"""
VSS SubLib — English property mapping (identity adapter).
============================================================
Maps English CSS property names to canonical CSS properties.
Also defines VSS keywords for the English frontend.
"""

from __future__ import annotations


# =============================================================================
#  Property mapping: VSS English name → CSS canonical name
# =============================================================================

PROPERTY_MAP: dict[str, str] = {
    # Layout
    "display": "display",
    "position": "position",
    "top": "top",
    "right": "right",
    "bottom": "bottom",
    "left": "left",
    "z_index": "z-index",
    "float": "float",
    "clear": "clear",
    "overflow": "overflow",
    "overflow_x": "overflow-x",
    "overflow_y": "overflow-y",
    "visibility": "visibility",
    "opacity": "opacity",

    # Flexbox
    "flex": "flex",
    "flex_direction": "flex-direction",
    "flex_wrap": "flex-wrap",
    "flex_grow": "flex-grow",
    "flex_shrink": "flex-shrink",
    "flex_basis": "flex-basis",
    "justify_content": "justify-content",
    "align_items": "align-items",
    "align_self": "align-self",
    "align_content": "align-content",
    "order": "order",
    "gap": "gap",
    "row_gap": "row-gap",
    "column_gap": "column-gap",

    # Grid
    "grid": "grid",
    "grid_template_columns": "grid-template-columns",
    "grid_template_rows": "grid-template-rows",
    "grid_column": "grid-column",
    "grid_row": "grid-row",
    "grid_area": "grid-area",
    "grid_gap": "grid-gap",

    # Box model
    "width": "width",
    "height": "height",
    "min_width": "min-width",
    "min_height": "min-height",
    "max_width": "max-width",
    "max_height": "max-height",
    "margin": "margin",
    "margin_top": "margin-top",
    "margin_right": "margin-right",
    "margin_bottom": "margin-bottom",
    "margin_left": "margin-left",
    "padding": "padding",
    "padding_top": "padding-top",
    "padding_right": "padding-right",
    "padding_bottom": "padding-bottom",
    "padding_left": "padding-left",
    "box_sizing": "box-sizing",

    # Border
    "border": "border",
    "border_top": "border-top",
    "border_right": "border-right",
    "border_bottom": "border-bottom",
    "border_left": "border-left",
    "border_radius": "border-radius",
    "border_color": "border-color",
    "border_width": "border-width",
    "border_style": "border-style",
    "outline": "outline",

    # Background
    "background": "background",
    "background_color": "background-color",
    "background_image": "background-image",
    "background_size": "background-size",
    "background_position": "background-position",
    "background_repeat": "background-repeat",

    # Typography
    "color": "color",
    "font": "font",
    "font_family": "font-family",
    "font_size": "font-size",
    "font_weight": "font-weight",
    "font_style": "font-style",
    "line_height": "line-height",
    "letter_spacing": "letter-spacing",
    "text_align": "text-align",
    "text_decoration": "text-decoration",
    "text_transform": "text-transform",
    "white_space": "white-space",
    "word_wrap": "word-wrap",
    "word_break": "word-break",

    # Effects
    "box_shadow": "box-shadow",
    "text_shadow": "text-shadow",
    "filter": "filter",
    "backdrop_filter": "backdrop-filter",

    # Transform & Animation
    "transform": "transform",
    "transform_origin": "transform-origin",
    "transition": "transition",
    "transition_property": "transition-property",
    "transition_duration": "transition-duration",
    "transition_timing_function": "transition-timing-function",
    "animation": "animation",
    "animation_name": "animation-name",
    "animation_duration": "animation-duration",

    # Interaction
    "cursor": "cursor",
    "pointer_events": "pointer-events",
    "user_select": "user-select",
    "resize": "resize",

    # Misc
    "content": "content",
    "list_style": "list-style",
    "table_layout": "table-layout",
    "vertical_align": "vertical-align",
    "object_fit": "object-fit",
    "object_position": "object-position",
    "aspect_ratio": "aspect-ratio",

    # Shorthand helpers (VSS-specific)
    "scale": "transform",           # scale: 0.98 → transform: scale(0.98)
    "rotate": "transform",          # rotate: 45deg → transform: rotate(45deg)
    "translate": "transform",       # translate: 10px 20px → transform: translate(10px, 20px)
}

# Shorthand properties that get special CSS generation
SHORTHAND_TRANSFORMS: dict[str, str] = {
    "scale": "scale({value})",
    "rotate": "rotate({value})",
    "translate": "translate({value})",
}

# Display shorthand aliases
DISPLAY_ALIASES: dict[str, str] = {
    "row": "flex; flex-direction: row",
    "column": "flex; flex-direction: column",
    "grid": "grid",
    "hidden": "none",
    "block": "block",
    "inline": "inline",
    "inline_block": "inline-block",
}


# =============================================================================
#  VSS Keywords — for tokenizer
# =============================================================================

KEYWORDS: dict[str, str] = {
    "theme": "THEME",
    "style": "STYLE",
    "mixin": "MIXIN",
    "keyframes": "KEYFRAMES",
    "end": "END",
    "when": "WHEN",
    "include": "INCLUDE",
    "apply": "APPLY",
    "important": "IMPORTANT",
}


def normalize_property(vss_prop: str) -> str:
    """Normalize a VSS property name to its CSS equivalent."""
    return PROPERTY_MAP.get(vss_prop, vss_prop.replace("_", "-"))
