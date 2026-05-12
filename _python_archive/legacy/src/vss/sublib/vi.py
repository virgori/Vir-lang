"""
VSS SubLib — Vietnamese property mapping.
===========================================
Maps Vietnamese CSS property names to canonical CSS properties.
Cho phép viết style bằng tiếng Việt.

Ví dụ: nền → background, đệm → padding, bo_tròn → border-radius
"""

from __future__ import annotations


# =============================================================================
#  Property mapping: Tiếng Việt → CSS canonical name
# =============================================================================

PROPERTY_MAP: dict[str, str] = {
    # Bố cục (Layout)
    "bố_cục": "display",
    "hiển_thị": "display",
    "vị_trí": "position",
    "trên": "top",
    "phải": "right",
    "dưới": "bottom",
    "trái": "left",
    "tầng": "z-index",
    "tràn": "overflow",
    "tràn_ngang": "overflow-x",
    "tràn_dọc": "overflow-y",
    "hiện": "visibility",
    "độ_mờ": "opacity",

    # Flexbox
    "dẻo": "flex",
    "hướng_dẻo": "flex-direction",
    "bọc_dẻo": "flex-wrap",
    "giãn": "flex-grow",
    "co": "flex-shrink",
    "dàn": "justify-content",
    "căn": "align-items",
    "tự_căn": "align-self",
    "căn_nội_dung": "align-content",
    "thứ_tự": "order",
    "khoảng_cách": "gap",
    "khoảng_hàng": "row-gap",
    "khoảng_cột": "column-gap",

    # Grid
    "lưới": "grid",
    "cột_lưới": "grid-template-columns",
    "hàng_lưới": "grid-template-rows",
    "vùng_lưới": "grid-area",

    # Kích thước (Dimensions)
    "rộng": "width",
    "chiều_rộng": "width",
    "cao": "height",
    "chiều_cao": "height",
    "rộng_tối_thiểu": "min-width",
    "cao_tối_thiểu": "min-height",
    "rộng_tối_đa": "max-width",
    "cao_tối_đa": "max-height",

    # Lề & Đệm (Margin & Padding)
    "lề": "margin",
    "lề_trên": "margin-top",
    "lề_phải": "margin-right",
    "lề_dưới": "margin-bottom",
    "lề_trái": "margin-left",
    "đệm": "padding",
    "đệm_trên": "padding-top",
    "đệm_phải": "padding-right",
    "đệm_dưới": "padding-bottom",
    "đệm_trái": "padding-left",
    "hộp": "box-sizing",

    # Viền (Border)
    "viền": "border",
    "viền_trên": "border-top",
    "viền_phải": "border-right",
    "viền_dưới": "border-bottom",
    "viền_trái": "border-left",
    "bo": "border-radius",
    "bo_tròn": "border-radius",
    "màu_viền": "border-color",
    "dày_viền": "border-width",
    "kiểu_viền": "border-style",
    "viền_ngoài": "outline",

    # Nền (Background)
    "nền": "background",
    "màu_nền": "background-color",
    "ảnh_nền": "background-image",
    "kích_nền": "background-size",
    "vị_trí_nền": "background-position",
    "lặp_nền": "background-repeat",

    # Chữ (Typography)
    "chữ": "color",
    "màu_chữ": "color",
    "màu": "color",
    "phông": "font",
    "họ_phông": "font-family",
    "cỡ_chữ": "font-size",
    "đậm": "font-weight",
    "nghiêng": "font-style",
    "chiều_cao_dòng": "line-height",
    "giãn_chữ": "letter-spacing",
    "canh_chữ": "text-align",
    "căn_chữ": "text-align",
    "trang_trí_chữ": "text-decoration",
    "biến_đổi_chữ": "text-transform",
    "khoảng_trắng": "white-space",
    "ngắt_từ": "word-break",

    # Hiệu ứng (Effects)
    "bóng": "box-shadow",
    "bóng_hộp": "box-shadow",
    "bóng_chữ": "text-shadow",
    "lọc": "filter",
    "lọc_nền": "backdrop-filter",

    # Biến đổi & Chuyển động (Transform & Animation)
    "biến_đổi": "transform",
    "gốc_biến_đổi": "transform-origin",
    "chuyển_động": "transition",
    "chuyển_tiếp": "transition",
    "hoạt_ảnh": "animation",
    "tên_hoạt_ảnh": "animation-name",
    "thời_gian_hoạt_ảnh": "animation-duration",
    "scale": "transform",
    "xoay": "transform",
    "dịch": "transform",

    # Tương tác (Interaction)
    "con_trỏ": "cursor",
    "sự_kiện_trỏ": "pointer-events",
    "chọn": "user-select",
    "thay_đổi_kích_thước": "resize",

    # Tỉ lệ
    "tỉ_lệ": "aspect-ratio",
    "vừa_vặn": "object-fit",
}

# Display shorthand aliases (tiếng Việt)
DISPLAY_ALIASES: dict[str, str] = {
    "hàng_ngang": "flex; flex-direction: row",
    "hàng_dọc": "flex; flex-direction: column",
    "lưới": "grid",
    "ẩn": "none",
    "khối": "block",
    "nội_tuyến": "inline",
}


# =============================================================================
#  VSS Keywords — tiếng Việt
# =============================================================================

KEYWORDS: dict[str, str] = {
    "chủ_đề": "THEME",
    "phong_cách": "STYLE",
    "kiểu": "STYLE",
    "trộn": "MIXIN",
    "khung_hình": "KEYFRAMES",
    "hết": "END",
    "kết_thúc": "END",
    "khi": "WHEN",
    "bao_gồm": "INCLUDE",
    "áp_dụng": "APPLY",
    "quan_trọng": "IMPORTANT",
}


def normalize_property(vss_prop: str) -> str:
    """Normalize a Vietnamese VSS property name to its CSS equivalent."""
    return PROPERTY_MAP.get(vss_prop, vss_prop.replace("_", "-"))
