from django import template
from django.templatetags.static import static
from django.utils.html import escape, format_html

register = template.Library()


@register.simple_tag
def icon(name, css_class="", label=""):
    """
    Render an icon from the self-hosted SVG sprite.

    Usage: {% icon "keys" "icon-sm text-gold" %}
    Icons are decorative by default (aria-hidden). Pass a label to make the
    icon meaningful to screen readers.
    """
    href = f"{static('icons/sprite.svg')}#{name}"
    classes = f"icon {css_class}".strip()
    if label:
        return format_html(
            '<svg class="{}" role="img" aria-label="{}"><use href="{}"></use></svg>',
            classes,
            escape(label),  # always escape, even template string literals (marked safe)
            href,
        )
    return format_html(
        '<svg class="{}" aria-hidden="true" focusable="false"><use href="{}"></use></svg>',
        classes,
        href,
    )
