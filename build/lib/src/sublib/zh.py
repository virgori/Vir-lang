"""
zh.py – Chinese SubLib Adapter (中文)
=======================================
Maps Chinese natural language phrases → lib TokenKind.
"""

from __future__ import annotations

from src.lib.keywords import TokenKind
from src.sublib.base import PhraseEntry, SubLibAdapter, SubLibRegistry


@SubLibRegistry.register
class ChineseAdapter(SubLibAdapter):
    """中文 → TokenKind 适配器"""

    @property
    def lang_code(self) -> str:
        return "zh"

    @property
    def lang_name(self) -> str:
        return "中文"

    def _define_phrases(self) -> list[PhraseEntry]:
        P = PhraseEntry
        K = TokenKind
        return [
            # ── 定义 ──────────────────────────────────────
            P("函数",       K.FUNC_DEF,     "definition"),
            P("定义函数",   K.FUNC_DEF,     "definition"),
            P("创建函数",   K.FUNC_DEF,     "definition"),
            P("声明函数",   K.FUNC_DEF,     "definition"),

            P("变量",       K.VAR_DECL,     "definition"),
            P("声明变量",   K.VAR_DECL,     "definition"),
            P("设置变量",   K.VAR_DECL,     "definition"),
            P("赋值",       K.VAR_DECL,     "definition"),
            P("令",         K.VAR_DECL,     "definition"),

            P("常量",       K.CONST_DECL,   "definition"),
            P("声明常量",   K.CONST_DECL,   "definition"),

            P("类",         K.CLASS_DEF,    "definition"),
            P("定义类",     K.CLASS_DEF,    "definition"),

            P("导入",       K.IMPORT,       "definition"),
            P("引入",       K.IMPORT,       "definition"),

            P("导出",       K.EXPORT,       "definition"),
            P("公开",       K.EXPORT,       "definition"),

            # ── 控制流 ────────────────────────────────────
            P("如果",       K.IF,           "control_flow"),
            P("假如",       K.IF,           "control_flow"),
            P("若",         K.IF,           "control_flow"),
            P("当",         K.IF,           "control_flow"),

            P("否则",       K.ELSE,         "control_flow"),
            P("不然",       K.ELSE,         "control_flow"),
            P("要不",       K.ELSE,         "control_flow"),

            P("否则如果",   K.EIF,         "control_flow"),
            P("要不如果",   K.EIF,         "control_flow"),

            P("循环",       K.LOOP,         "control_flow"),
            P("重复",       K.LOOP,         "control_flow"),
            P("重复执行",   K.LOOP,         "control_flow"),

            P("当…时",      K.WHEN,        "control_flow"),
            P("只要",       K.WHEN,        "control_flow"),
            P("一直",       K.WHEN,        "control_flow"),

            P("遍历",       K.FOR,          "control_flow"),
            P("对于每个",   K.FOR,          "control_flow"),
            P("对每个",     K.FOR,          "control_flow"),

            P("跳出",       K.BREAK,        "control_flow"),
            P("中断",       K.BREAK,        "control_flow"),
            P("退出循环",   K.BREAK,        "control_flow"),

            P("继续",       K.SKIP,        "control_flow"),
            P("跳过",       K.SKIP,        "control_flow"),

            P("返回",       K.OUT,         "control_flow"),
            P("结果是",     K.OUT,         "control_flow"),
            P("回传",       K.OUT,         "control_flow"),

            P("匹配",       K.CASE,        "control_flow"),
            P("情况",       K.CASE,        "control_flow"),

            # ── 算术 ──────────────────────────────────────
            P("加",         K.OP_ADD,       "arithmetic"),
            P("加法",       K.OP_ADD,       "arithmetic"),
            P("相加",       K.OP_ADD,       "arithmetic"),
            P("求和",       K.OP_ADD,       "arithmetic"),

            P("减",         K.OP_SUB,       "arithmetic"),
            P("减法",       K.OP_SUB,       "arithmetic"),
            P("相减",       K.OP_SUB,       "arithmetic"),

            P("乘",         K.OP_MUL,       "arithmetic"),
            P("乘法",       K.OP_MUL,       "arithmetic"),
            P("相乘",       K.OP_MUL,       "arithmetic"),

            P("除",         K.OP_DIV,       "arithmetic"),
            P("除法",       K.OP_DIV,       "arithmetic"),
            P("相除",       K.OP_DIV,       "arithmetic"),
            P("除以",       K.OP_DIV,       "arithmetic"),

            P("取余",       K.OP_MOD,       "arithmetic"),
            P("取模",       K.OP_MOD,       "arithmetic"),

            P("幂",         K.OP_POW,       "arithmetic"),
            P("次方",       K.OP_POW,       "arithmetic"),

            # ── 比较 ──────────────────────────────────────
            P("等于",       K.CMP_EQ,       "comparison"),
            P("相等",       K.CMP_EQ,       "comparison"),

            P("不等于",     K.CMP_NE,       "comparison"),
            P("不相等",     K.CMP_NE,       "comparison"),

            P("大于",       K.CMP_GT,       "comparison"),
            P("比…大",      K.CMP_GT,       "comparison"),

            P("小于",       K.CMP_LT,       "comparison"),
            P("比…小",      K.CMP_LT,       "comparison"),

            P("大于等于",   K.CMP_GE,       "comparison"),
            P("不小于",     K.CMP_GE,       "comparison"),

            P("小于等于",   K.CMP_LE,       "comparison"),
            P("不大于",     K.CMP_LE,       "comparison"),

            # ── 逻辑 ──────────────────────────────────────
            P("并且",       K.LOGIC_AND,    "logical"),
            P("而且",       K.LOGIC_AND,    "logical"),

            P("或者",       K.LOGIC_OR,     "logical"),
            P("或",         K.LOGIC_OR,     "logical"),

            P("取反",       K.LOGIC_NOT,    "logical"),
            P("不是",       K.LOGIC_NOT,    "logical"),

            # ── 输入输出 ──────────────────────────────────
            P("打印",       K.PRINT,        "io"),
            P("输出",       K.PRINT,        "io"),
            P("显示",       K.PRINT,        "io"),
            P("写出",       K.PRINT,        "io"),

            P("输入",       K.INPUT,        "io"),
            P("读取",       K.INPUT,        "io"),
            P("从键盘读取", K.INPUT,        "io"),

            # ── 类型 ──────────────────────────────────────
            P("整数",       K.TYPE_INT,     "type"),
            P("浮点数",     K.TYPE_FLOAT,   "type"),
            P("字符串",     K.TYPE_STRING,  "type"),
            P("布尔",       K.TYPE_BOOL,    "type"),
            P("数组",       K.TYPE_ARRAY,   "type"),
            P("字典",       K.TYPE_MAP,     "type"),

            # ── 布尔 / 空 ─────────────────────────────────
            P("真",         K.TRUE,         "literal"),
            P("假",         K.FALSE,        "literal"),
            P("空",         K.NONE,         "literal"),

            # ── 系统 ──────────────────────────────────────
            P("检查处理器",  K.CHECK_CPU,   "system"),
            P("处理器空闲",  K.CHECK_CPU,   "system"),

            P("热补丁",     K.PATCH,        "system"),
            P("优化",       K.PATCH,        "system"),

            P("寄存器",     K.TARGET_REGISTER, "system"),
            P("用寄存器",   K.TARGET_REGISTER, "system"),

            P("执行",       K.EXECUTE,      "system"),
            P("运行",       K.EXECUTE,      "system"),
            P("开始",       K.EXECUTE,      "system"),

            P("休眠",       K.SLEEP,        "system"),
            P("等待",       K.SLEEP,        "system"),
        ]

    def _define_stop_words(self) -> list[str]:
        return [
            "的", "了", "在", "是", "我", "有", "和", "就",
            "不", "人", "都", "一", "一个", "上", "也", "很",
            "到", "说", "要", "去", "你", "会", "着", "没有",
            "看", "好", "自己", "这", "他", "她", "它",
            "吗", "吧", "呢", "啊", "嘛", "哦", "哈",
        ]
