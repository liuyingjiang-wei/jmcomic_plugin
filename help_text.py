from __future__ import annotations

from jmcomic_plugin.config import get_jmcomic_settings


def build_jm_help_message(*, channel: str = "qq") -> str:
    settings = get_jmcomic_settings()
    chepai = "已开启" if settings.qq.chepai_enabled else "已关闭"
    ch = (channel or "qq").strip().lower()

    lines = [
        "【JMComic 插件帮助】",
        "",
        "本插件提供禁漫天堂搜索、下载与 PDF 导出。",
        "",
    ]

    if ch == "telegram":
        lines.extend(
            [
                "■ Telegram 用法",
                "· 直接对 Bot 说自然语言，例如：",
                "  「搜索 JM 关键词 xxx」",
                "  「下载本子 123456 并导出 PDF」",
                "· 需使用带 Agent 工具的模式（ReAct / Plan 等），",
                "  助手会调用 jmcomic_search / jmcomic_download。",
                "",
            ]
        )
    else:
        lines.extend(
            [
                "■ QQ 快捷指令（无需 @ 机器人）",
                f"· #车牌 + 数字相册 ID（当前：{chepai}）",
                "  示例：#车牌123456",
                "  流程：提示「正在处理…」→ 下载并导出 PDF → 发文件/群文件/直链",
                "",
                "■ 与机器人对话（需 @ 或私聊前缀触发时）",
                "· 可说：「搜索 JM xxx」「下载本子 123456」",
                "  Agent 会调用 jmcomic_search / jmcomic_download。",
                "",
            ]
        )

    lines.extend(
        [
            "■ Agent 工具",
            "· jmcomic_search(query, page=1) — 站内搜索",
            "· jmcomic_download(album_id) — 下载并导出 PDF",
            "",
            "■ HTTP API（需 API Key）",
            "· GET  /api/jmcomic/search?q=关键词&page=1",
            "· POST /api/jmcomic/download  Body: {\"album_id\":\"123456\"}",
            "",
            "■ 常用配置（data/jmcomic/config.yaml）",
            "· client.impl: api（无代理推荐）| html",
            "· public_base_url — QQ 发文件失败时的 PDF 直链根地址",
            "· qq.chepai_enabled — 是否响应 #车牌",
            "· qq.recall_delay_sec — 撤回提示消息延迟（秒）",
            "",
            "■ 排错",
            "· #车牌无响应：确认已加载 qq-onebot 与本插件",
            "· 搜索超时：client.impl 改为 api，检查代理设置",
            "· 群聊收不到 PDF：配置公网可访问的 public_base_url",
            "",
            "发送「jm帮助」可随时查看本说明。",
        ]
    )

    return "\n".join(lines)
