# Copyright (c) 2016, Isotoma Limited
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#     * Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#     * Neither the name of the Isotoma Limited nor the
#       names of its contributors may be used to endorse or promote products
#       derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL ISOTOMA LIMITED BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF
# THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import json

from django.forms import widgets
from django.utils import translation
from django.utils.functional import cached_property

from wagtail.core.rich_text import features as feature_registry
from wagtail.utils.widgets import WidgetWithScript
from wagtail.admin.edit_handlers import RichTextFieldPanel
from wagtail.core.rich_text.rewriters import EmbedRewriter, LinkRewriter, MultiRuleRewriter
from wagtail.admin.rich_text.converters.editor_html import DbWhitelister, EmbedTypeRule, LinkTypeRule


class DbTinymceWhitelister(DbWhitelister):
    """
    A custom whitelisting engine to convert the HTML as returned by the rich text editor
    into the pseudo-HTML format stored in the database (in which images, documents and other
    linked objects are identified by ID rather than URL):

    * implements a 'construct_whitelister_element_rules' hook so that other apps can modify
      the whitelist ruleset (e.g. to permit additional HTML elements beyond those in the base
      Whitelister module);
    * replaces any element with a 'data-embedtype' attribute with an <embed> element, with
      attributes supplied by the handler for that type as defined in EMBED_HANDLERS;
    * rewrites the attributes of any <a> element with a 'data-linktype' attribute, as
      determined by the handler for that type defined in LINK_HANDLERS, while keeping the
      element content intact.
    """

    def clean_tag_node(self, doc, tag):
        if 'data-embedtype' in tag.attrs:
            embed_type = tag['data-embedtype']
            # fetch the appropriate embed handler for this embedtype
            try:
                embed_handler = self.embed_handlers[embed_type]
            except KeyError:
                # discard embeds with unrecognised embedtypes
                tag.decompose()
                return

            embed_attrs = embed_handler.get_db_attributes(tag)
            embed_attrs['embedtype'] = embed_type

            embed_tag = doc.new_tag('embed', **embed_attrs)
            embed_tag.can_be_empty_element = True
            tag.replace_with(embed_tag)
        elif tag.name == 'a' and 'data-linktype' in tag.attrs:
            # first, whitelist the contents of this tag
            for child in tag.contents:
                self.clean_node(doc, child)

            link_type = tag['data-linktype']
            try:
                link_handler = self.link_handlers[link_type]
            except KeyError:
                # discard links with unrecognised linktypes
                tag.unwrap()
                return

            link_attrs = link_handler.get_db_attributes(tag)
            link_attrs['linktype'] = link_type
            tag.attrs.clear()
            tag.attrs.update(**link_attrs)
        else:
            if tag.name == 'div':
                tag.name = 'p'

            super(DbWhitelister, self).clean_tag_node(doc, tag)


class EditorTinymceHTMLConverter:
    def __init__(self, features=None):
        if features is None:
            features = feature_registry.get_default_features()

        self.converter_rules = []
        for feature in features:
            rule = feature_registry.get_converter_rule('tinymceeditorhtml', feature)
            if rule is not None:
                # rule should be a list of WhitelistRule() instances - append this to
                # the master converter_rules list
                self.converter_rules.extend(rule)

    @cached_property
    def whitelister(self):
        return DbTinymceWhitelister(self.converter_rules)

    def to_database_format(self, html):
        return self.whitelister.clean(html)

    @cached_property
    def html_rewriter(self):
        embed_rules = {}
        link_rules = {}
        for rule in self.converter_rules:
            if isinstance(rule, EmbedTypeRule):
                embed_rules[rule.embed_type] = rule.handler.expand_db_attributes
            elif isinstance(rule, LinkTypeRule):
                link_rules[rule.link_type] = rule.handler.expand_db_attributes

        return MultiRuleRewriter([
            LinkRewriter(link_rules), EmbedRewriter(embed_rules)
        ])

    def from_database_format(self, html):
        return self.html_rewriter(html)


class TinyMCERichTextArea(WidgetWithScript, widgets.Textarea):
    accepts_features = True

    @classmethod
    def getDefaultArgs(cls):
        return {
            'buttons': [
                [
                    ['undo', 'redo'],
                    ['styleselect'],
                    ['bold', 'italic'],
                    ['bullist', 'numlist', 'outdent', 'indent'],
                    ['table'],
                    ['link', 'unlink'],
                    ['wagtaildoclink', 'wagtailimage', 'wagtailembed'],
                    ['pastetext', 'fullscreen'],
                ]
            ],
            'menus': False,
            'options': {
                'browser_spellcheck': True,
                'noneditable_leave_contenteditable': True,
                'language': translation.to_locale(translation.get_language() or 'en'),
                'language_load': True,
            },
        }

    def __init__(self, attrs=None, **kwargs):
        self.options = kwargs.pop('options', None)

        self.features = kwargs.pop('features', None)
        if self.features is None:
            self.features = feature_registry.get_default_features()

        self.converter = EditorTinymceHTMLConverter(self.features)

        self.kwargs = self.getDefaultArgs()
        if kwargs is not None:
            self.kwargs.update(kwargs)
        if self.options is not None:
            self.kwargs.update(self.options)

        super().__init__(attrs)

    def get_panel(self):
        return RichTextFieldPanel

    def render(self, name, value, attrs=None, renderer=None):
        if value is None:
            translated_value = None
        else:
            translated_value = self.converter.from_database_format(value)
        return super().render(name, translated_value, attrs, renderer)

    def render_js_init(self, id_, name, value):
        options = self.kwargs.get('options')
        if options:
            kwargs = options.copy()
        else:
            kwargs = {}

        buttons = self.kwargs.get('buttons')
        if buttons:
            kwargs['toolbar'] = [
                ' | '.join([' '.join(groups) for groups in rows])
                for rows in self.kwargs['buttons']
            ]
        else:
            kwargs['toolbar'] = False

        menus = self.kwargs.get('menus')
        if menus:
            kwargs['menubar'] = ' '.join(self.kwargs['menus'])
        else:
            kwargs['menubar'] = False

        language = self.kwargs.get('language')
        if not language or language == 'en_US':
            kwargs['language'] = 'en'
        else:
            kwargs['language'] = language

        return "makeTinyMCEEditable({0}, {1});".format(json.dumps(id_), json.dumps(kwargs))

    def value_from_datadict(self, data, files, name):
        original_value = super().value_from_datadict(data, files, name)
        if original_value is None:
            return None
        return self.converter.to_database_format(original_value)

