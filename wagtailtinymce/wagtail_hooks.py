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

from django.urls import reverse
from django.templatetags.static import static
from django.utils import translation
from django.utils.html import escape
from django.utils.html import format_html
from django.utils.html import format_html_join
from django.utils.safestring import mark_safe

from wagtail.admin.templatetags.wagtailadmin_tags import hook_output
from wagtail.admin.rich_text.converters.editor_html import LinkTypeRule, WhitelistRule
from wagtail.core.whitelist import allow_without_attributes, attribute_rule, check_url
from wagtail.core import hooks
from wagtail.core.rich_text.pages import PageLinkHandler
from wagtail.images.rich_text.editor_html import EditorHTMLImageConversionRule
from wagtail.documents.rich_text.editor_html import EditorHTMLDocumentLinkConversionRule


def to_js_primitive(string):
    return mark_safe(json.dumps(escape(string)))


@hooks.register('insert_editor_css')
def insert_editor_css():
    css_files = [
        'wagtailtinymce/css/icons.css'
    ]
    css_includes = format_html_join(
        '\n',
        '<link rel="stylesheet" href="{0}">',
        ((static(filename),) for filename in css_files),
    )
    return css_includes + hook_output('insert_tinymce_css')


@hooks.register('insert_editor_js')
def insert_editor_js():
    preload = format_html(
        '<script>'
        '(function() {{'
        '    "use strict";'
        '    window.tinymce = window.tinymce || {{}};'
        '    window.tinymce.base = window.tinymce.baseURL = {};'
        '    window.tinymce.suffix = "";'
        '}}());'
        '</script>',
        to_js_primitive(static('wagtailtinymce/js/vendor/tinymce')),
    )
    js_files = [
        'wagtailtinymce/js/vendor/tinymce/jquery.tinymce.min.js',
        'wagtailtinymce/js/vendor/tinymce/tinymce.min.js',
        'wagtailtinymce/js/tinymce-editor.js',
        'wagtailadmin/js/page-chooser-modal.js',
        'wagtailimages/js/image-chooser-modal.js',
        'wagtaildocs/js/document-chooser-modal.js',
        'wagtailembeds/js/embed-chooser-modal.js',
    ]
    js_includes = format_html_join(
        '\n',
        '<script src="{0}"></script>',
        ((static(filename),) for filename in js_files)
    )
    return preload + js_includes + hook_output('insert_tinymce_js')


@hooks.register('insert_tinymce_js')
def images_richtexteditor_js():
    return format_html(
        """
        <script>
            registerMCEPlugin("wagtailimage", {}, {});
            window.chooserUrls.imageChooserSelectFormat = {};
        </script>
        """,
        to_js_primitive(static('wagtailtinymce/js/tinymce-plugins/wagtailimage.js')),
        to_js_primitive(translation.to_locale(translation.get_language())),
        to_js_primitive(reverse('wagtailimages:chooser_select_format', args=['00000000']))
    )


@hooks.register('insert_tinymce_js')
def embeds_richtexteditor_js():
    return format_html(
        """
        <script>
            registerMCEPlugin("wagtailembeds", {}, {});
        </script>
        """,
        to_js_primitive(static('wagtailtinymce/js/tinymce-plugins/wagtailembeds.js')),
        to_js_primitive(translation.to_locale(translation.get_language())),
    )


@hooks.register('insert_tinymce_js')
def links_richtexteditor_js():
    return format_html(
        """
        <script>
            registerMCEPlugin("wagtaillink", {}, {});
        </script>
        """,
        to_js_primitive(static('wagtailtinymce/js/tinymce-plugins/wagtaillink.js')),
        to_js_primitive(translation.to_locale(translation.get_language())),
    )


@hooks.register('insert_tinymce_js')
def docs_richtexteditor_js():
    return format_html(
        """
        <script>
            registerMCEPlugin("wagtaildoclink", {}, {});
        </script>
        """,
        to_js_primitive(static('wagtailtinymce/js/tinymce-plugins/wagtaildoclink.js')),
        to_js_primitive(translation.to_locale(translation.get_language())),
    )


ALLOWED_ATTR = dict.fromkeys(
    ['border', 'cellpadding', 'cellspacing', 'style', 'width', 'colspan', 'margin-left',
     'margin-right', 'height', 'border-color', 'text-align', 'background-color',
     'vertical-align', 'scope', 'font-family', 'rowspan', 'valign', 'class'],
    True)


default_attribute_rule = attribute_rule(ALLOWED_ATTR)


@hooks.register('register_rich_text_features')
def register_tinymce_features(features):
    features.register_converter_rule('tinymceeditorhtml', 'link', [
        WhitelistRule('a', attribute_rule({'href': check_url})),
        LinkTypeRule('page', PageLinkHandler),
    ])
    features.register_converter_rule('tinymceeditorhtml', 'bold', [
        WhitelistRule('b', allow_without_attributes),
        WhitelistRule('strong', allow_without_attributes),
    ])
    features.register_converter_rule('tinymceeditorhtml', 'br', [
        WhitelistRule('br', allow_without_attributes),
    ])
    features.register_converter_rule('tinymceeditorhtml', 'div', [
        WhitelistRule('div', allow_without_attributes),
    ])
    features.register_converter_rule('tinymceeditorhtml', 'italic', [
        WhitelistRule('i', allow_without_attributes),
        WhitelistRule('em', allow_without_attributes),
    ])
    for element in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
        features.register_converter_rule('tinymceeditorhtml', element, [
            WhitelistRule(element, allow_without_attributes)
        ])
    features.register_converter_rule('tinymceeditorhtml', 'hr', [
        WhitelistRule('hr', allow_without_attributes)
    ])

    features.register_converter_rule('tinymceeditorhtml', 'ol', [
        WhitelistRule('ol', allow_without_attributes),
        WhitelistRule('li', allow_without_attributes),
    ])
    features.register_converter_rule('tinymceeditorhtml', 'ul', [
        WhitelistRule('ul', allow_without_attributes),
        WhitelistRule('li', allow_without_attributes),
    ])
    features.register_converter_rule('tinymceeditorhtml', 'p', [
        WhitelistRule('p', allow_without_attributes)
    ])
    features.register_converter_rule('tinymceeditorhtml', 'subscripts', [
        WhitelistRule('sub', allow_without_attributes),
        WhitelistRule('sup', allow_without_attributes)
    ])
    features.register_converter_rule('tinymceeditorhtml', 'blockquote', [
        WhitelistRule('blockquote', allow_without_attributes)
    ])
    features.register_converter_rule('tinymceeditorhtml', 'code', [
        WhitelistRule('pre', allow_without_attributes),
        WhitelistRule('code', allow_without_attributes)
    ])

    features.register_converter_rule('tinymceeditorhtml', 'table', [
        WhitelistRule(element, default_attribute_rule) for element in
        ['table', 'caption', 'tbody', 'th', 'tr', 'td']
    ])

    features.register_converter_rule('tinymceeditorhtml', 'image', EditorHTMLImageConversionRule)
    features.register_converter_rule(
        'tinymceeditorhtml', 'document-link', EditorHTMLDocumentLinkConversionRule
    )

    features.default_features.append('subscripts')
    features.default_features.append('blockquote')
    features.default_features.append('code')
    features.default_features.append('table')

