import unicodedata

from langchain_core.callbacks import dispatch_custom_event


def cell_display_length(s):
    """计算字符串显示宽度，中文等全角字符算2，半角算1"""
    length = 0
    for c in str(s):
        # F,W,? 算2，其它算1
        length += 2 if unicodedata.east_asian_width(c) in "FW" else 1
    return length


def pretty_table(header, rows):
    columns = [[header[i]] + [row[i] for row in rows] for i in range(len(header))]
    col_widths = [max(cell_display_length(cell) for cell in col) for col in columns]

    def format_row(row):
        formatted = []
        for idx, cell in enumerate(row):
            cell_str = str(cell)
            # add spaces (全宽字符用2宽度补齐)
            padding = col_widths[idx] - cell_display_length(cell_str)
            formatted.append(cell_str + " " * padding)
        return " | ".join(formatted)

    sep = "-+-".join(["-" * w for w in col_widths])

    lines = [
        format_row(header),
        sep,
    ]
    for row in rows:
        lines.append(format_row(row))
    return "\n".join(lines)


def build_table(title, data_list, empty_msg="为空"):
    """辅助函数：构建表格内容"""
    if not data_list:
        return f"{title}{empty_msg}\n\n"
    return f"{title}：\n\n{pretty_table(['资源类别', '资源ID'], data_list)}\n\n"


def conditional_dispatch_custom_event(name, data, **kwargs):
    if kwargs.get("enable_custom_event", True):
        dispatch_custom_event(name, data)
