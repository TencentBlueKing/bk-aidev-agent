import ast


def extract_error_message(error_string):
    start = error_string.find("{")
    end = error_string.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            json_str = error_string[start : end + 1]
            data = ast.literal_eval(json_str)
            return data.get("message", "")
        except (ValueError, SyntaxError):
            return None
    return None
