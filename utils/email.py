"""
Email sending utilities for the reservation app.
"""

import re
from typing import Dict

from inscriptis import get_annotated_text
from inscriptis.model.config import ParserConfig
from inscriptis.model.tag import CustomHtmlTagHandlerMapping
from inscriptis.model.html_document_state import HtmlDocumentState
from inscriptis.css_profiles import CSS_PROFILES, HtmlElement


def convert_html_to_text(html_message: str) -> str:
    """
    HTMLメール文章をテキストに変換します。
    """

    # カスタムハンドラの定義
    def a_start_handler(state: HtmlDocumentState, attrs: Dict) -> None:
        state.link_target = ""
        state.link_target = attrs.get("href", "")

        if state.link_target:
            state.tags[-1].write("[")

    def a_end_handler(state: HtmlDocumentState) -> None:
        if state.link_target:
            state.tags[-1].write(f"]({state.link_target})")

    # inscriptisで変換
    # config = ParserConfig(display_links=True, annotation_rules={"a": ["link"]})
    css = CSS_PROFILES["strict"].copy()
    css["body"] = HtmlElement(margin_before=0)
    custom_mapping = CustomHtmlTagHandlerMapping(start_tag_mapping={"a": a_start_handler}, end_tag_mapping={"a": a_end_handler})
    annotation_rules = {"a": ["link"]}
    config = ParserConfig(css=css, custom_html_tag_handler_mapping=custom_mapping, annotation_rules=annotation_rules)
    result = get_annotated_text(html_message, config)
    text_message = result["text"]

    # 置換リスト作成
    replacements = []
    for start_pos, end_pos, labels in result.get("label", []):
        if "link" in labels:
            # [を足した分を戻す
            start_pos = start_pos - 1
            # 対象の位置を取得
            original_text = text_message[start_pos:end_pos]

            # [文字列](URL)の形式の場合に文字列\nURLに変更
            # ただし、文字列とURLが同一の場合はURLのみに変更
            # 正規表現で抽出し、このルールでnew_textを生成
            match = re.match(r"\[(.*?)\]\((.*?)\)", original_text)
            if match:
                text_part = match.group(1)
                url = match.group(2)

                if text_part.strip() == url:
                    new_text = url
                else:
                    new_text = f"{text_part}\n{url}"

                replacements.append((start_pos, end_pos, original_text, new_text))

    # 後ろから置き換え処理
    for start_pos, end_pos, original_text, new_text in sorted(replacements, reverse=True):
        # 指定位置の現在の文字を取得し元の文字列と同一であればnew_textに変更
        current_text = text_message[start_pos:end_pos]
        if current_text == original_text:
            text_message = text_message[:start_pos] + new_text + text_message[end_pos:]

    # 前後の改行やスペースを削除
    text_message = text_message.strip()

    return text_message
