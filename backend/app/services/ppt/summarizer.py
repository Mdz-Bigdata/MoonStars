"""
大纲生成服务
使用 LLM 将网页内容转化为 PPT 大纲。
支持多模型：DeepSeek / GPT / Gemini / Claude
"""
import logging
from typing import List
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from app.core.config import settings
from .models import ScrapedContent, PPTOutline

logger = logging.getLogger(__name__)


class SummarizerService:
    """PPT 大纲生成服务"""

    def __init__(self, model_override: str = None, api_key: str = None, base_url: str = None):
        """
        初始化大纲生成服务。

        Args:
            model_override: 覆盖默认模型
            api_key: 覆盖默认 API Key
            base_url: 覆盖默认 Base URL
        """
        # NOTE: 支持多模型切换
        effective_model = model_override or settings.AI_DEFAULT_MODEL
        effective_key = api_key or settings.DEEPSEEK_API_KEY or settings.AI_API_KEY
        effective_base = base_url or settings.AI_BASE_URL

        self.llm = ChatOpenAI(
            api_key=effective_key,
            base_url=effective_base,
            model=effective_model,
            temperature=0.3,
        )
        self.parser = JsonOutputParser(pydantic_object=PPTOutline)

    async def generate_outline(
        self,
        contents: List[ScrapedContent],
        mode: str = "summarize",
        max_slides: int = 10,
        language: str = "zh-CN",
    ) -> PPTOutline:
        """
        生成 PPT 大纲。

        Args:
            contents: 爬取的网页内容列表
            mode: 生成模式（summarize=总结提取, convert=严格结构保持）
            max_slides: 最大幻灯片数量
            language: 输出语言

        Returns:
            PPT 大纲
        """
        system_prompt = self._get_system_prompt(mode, language, len(contents) > 1)
        user_prompt = self._get_user_prompt(contents, mode, max_slides, language)

        prompt = ChatPromptTemplate.from_messages(
            [("system", system_prompt), ("human", user_prompt)]
        )

        chain = prompt | self.llm | self.parser

        try:
            raw_output = await chain.ainvoke({})
            if isinstance(raw_output, dict):
                return PPTOutline.model_validate(raw_output)
            return raw_output
        except Exception as e:
            logger.error(f"大纲生成失败: {e}")
            raise e

    async def generate_outline_from_prompt(
        self,
        prompt: str,
        max_slides: int = 10,
        language: str = "zh-CN",
    ) -> PPTOutline:
        """
        根据用户的一句话/提示词直接生成 PPT 大纲。
        不依赖 URL，适用于从零创建专业演示文稿。

        Args:
            prompt: 用户提示词（如 "介绍人工智能的发展历程和未来趋势"）
            max_slides: 最大幻灯片数量
            language: 输出语言
        """
        lang_instruction = (
            "请使用中文生成所有内容。"
            if "zh" in language.lower()
            else "Please generate all content in English."
        )

        system_prompt = f"""你是一位世界级的 PPT 制作专家和战略咨询顾问。
根据用户提供的主题或一句话提示，从零创建一份专业、有深度、有逻辑的演示文稿大纲。

{lang_instruction}

要求：
1. **专业深度**：内容必须体现专业知识和行业洞察，不能停留在表面。
2. **逻辑清晰**：章节之间有递进关系，从背景 → 核心内容 → 分析 → 总结。
3. **视觉优先**：为每页选择合适的 `layout_type` 和 `visual_type`：
   - 知识层级 → `visual_type: "mindmap"`，并在 `mermaid` 字段写完整的 Mermaid mindmap 语法
   - 流程逻辑 → `visual_type: "flowchart"`，并在 `mermaid` 字段写完整的 Mermaid flowchart 语法
   - 系统架构 → `visual_type: "architecture"`，并在 `mermaid` 字段写完整的 Mermaid graph 语法
   - 概念展示 → `visual_type: "image"`，并在 `visual_prompt` 字段提供精美的英文图片描述
4. **版式选择**：每页填入 `layout_type`（text_only / text_image / full_image / two_column / diagram）。
5. **数据驱动**：尽可能包含合理的数据和案例来支撑观点。
6. **Mermaid 语法要求**：
   - mindmap 示例：mindmap\\n  root((主题))\\n    分支1\\n      子节点\\n    分支2
   - flowchart 示例：flowchart TD\\n  A[开始] --> B{{{{判断}}}}\\n  B -->|是| C[结束]
   - graph 示例：graph LR\\n  A[模块A] --> B[模块B]
   - 注意：Mermaid 代码中不要使用中文括号，不要包含 ```mermaid 标记

**输出 JSON 必须包含以下顶级字段**：
- `title`: 演示文稿标题
- `subtitle`: 副标题
- `sections`: 章节数组，每个章节包含 title, points, 以及可选的 mermaid, visual_type, visual_prompt, layout_type
- `conclusion`: 总结要点数组（3-5 个简短总结句）

注意：输出必须严格遵循 JSON 格式，不要包含任何 Markdown 代码块或多余文字。
"""

        format_instr = self.parser.get_format_instructions()
        format_instr = format_instr.replace("{", "{{").replace("}", "}}")

        user_prompt = f"""请根据以下主题创建一份专业的 PPT 大纲：

主题: {prompt}

要求：
- 使用 {language} 语言
- 生成 {max_slides} 页左右的幻灯片（sections 数量）
- 包含封面 title 和 subtitle
- 每个章节 3-6 个要点（points）
- 至少 50% 的章节包含 mermaid 图表（mindmap 或 flowchart），用于可视化知识结构或流程
- 为适合配图的页面提供英文 visual_prompt 描述
- 为每页选择最佳版式 layout_type
- 必须包含 conclusion 字段（3-5 个总结要点）
- 只输出纯 JSON，不要输出额外的解释文字

{format_instr}
"""

        prompt_template = ChatPromptTemplate.from_messages(
            [("system", system_prompt), ("human", user_prompt)]
        )
        chain = prompt_template | self.llm | self.parser

        try:
            raw_output = await chain.ainvoke({})
            # NOTE: 自动补全 LLM 可能遗漏的字段
            if isinstance(raw_output, dict):
                if "conclusion" not in raw_output or not raw_output["conclusion"]:
                    raw_output["conclusion"] = ["以上为本次演示的核心内容总结。"]
                if "subtitle" not in raw_output:
                    raw_output["subtitle"] = ""
                return PPTOutline.model_validate(raw_output)
            return raw_output
        except Exception as e:
            logger.error(f"提示词大纲生成失败: {e}")
            raise e

    def _get_system_prompt(self, mode: str, language: str, is_multi: bool) -> str:
        lang_instruction = (
            "请务必使用中文生成所有内容。"
            if "zh" in language.lower()
            else "Please generate all content in English."
        )

        common = """
1. **严格基于原文**：所有内容必须来源于提供的文档，严禁脱离原文进行发挥或虚构。
2. **深度沉淀**：不要只抓取表面关键词，要深入理解文章的论点、论据、逻辑结构及核心数据。
3. **逻辑性**：确保每一页幻灯片之间有逻辑递进关系，章节标题必须带观点。
"""
        # NOTE: 新增 layout_type 指引
        layout_hint = """
4. **版式选择 (Layout)**：为每页幻灯片选择最佳版式，填入 `layout_type` 字段。可选值：
   - "text_only" - 纯文字
   - "text_image" - 左文右图
   - "full_image" - 全图+文字叠加（适合概念展示）
   - "two_column" - 双栏对比
   - "diagram" - 以图表为主
"""

        if mode == "summarize":
            task = "进行综合性深度提炼" if is_multi else "进行深度解析和观点提取"
            return f"""你是一个顶级战略咨询顾问。任务是{task}，将文档转化为高价值、高 correlation 的PPT大纲。
{lang_instruction}
{common}
{layout_hint}
1. **视觉优先 (Visual-First)**：为每一页幻灯片生成视觉化内容。如果是复杂的知识点或层级结构，必须生成 `mermaid` 的 `mindmap` 类型。如果是流程或逻辑，生成 `flowchart`。如果是具象场景，设置 `visual_type` 为 'image' 并提供精美的 `visual_prompt`。
2. **知识脑图 (Mind Maps)**：对于知识体系，强制使用 Mermaid `mindmap` 语法。
3. **高保真 (100% Fidelity)**：即使是总结模式，也要确保关键观点不遗漏。
注意：输出必须严格遵循 JSON 格式，不要包含任何 Markdown 代码块或多余文字。
"""
        else:
            return f"""你是一个顶级的 PPT 制作专家 and 文档处理器。任务是按 **1:1 的结构和比例** 将网页文章转化为 PPT。
{lang_instruction}
{common}
{layout_hint}
1. **结构绝对对齐**：章节标题必须与原文的 H1/H2 标题完美一致，严禁总结或跳过。
2. **内容零遗漏**：所有原文观点、逻辑、数据都必须体现在 PPT 要点（points）中。
3. **强制视觉化**：每页幻灯片必须包含视觉内容。
   - 知识层级 -> `mindmap`
   - 流程逻辑 -> `flowchart`
   - 概念展示 -> `visual_type`: 'image'
4. **视觉碎片映射**：如果原文有表格或截图（见"视觉碎片"列表），必须填入其 `visual_fragment_id`。
"""

    def _get_user_prompt(
        self, contents: List[ScrapedContent], mode: str, max_slides: int, language: str
    ) -> str:
        docs_text = ""
        for i, c in enumerate(contents):
            docs_text += f"\n--- 文档 {i + 1} ---\n标题：{c.title}\n内容：{c.content[:20000]}\n"
            if c.tables:
                docs_text += "表格数据参考：\n" + "\n".join(c.tables) + "\n"
            if c.visual_fragments:
                docs_text += "可用视觉碎片(element screenshots):\n"
                for f in c.visual_fragments:
                    docs_text += f"- ID: {f.id}, 类型: {f.type}, 说明: {f.caption}\n"

        format_instr = self.parser.get_format_instructions()
        format_instr = format_instr.replace("{", "{{").replace("}", "}}")

        common = f"""
1. 使用 {language} 语言。
2. 每个章节必须包含 3-8 个要点（points）。
3. **视觉对齐 (Visual Fidelity)**：如果文档中包含表格、画板、架构图或截图，并且在"可用视觉碎片"中有对应的 ID，请**务必**在对应章节的 `visual_fragment_id` 字段中填写该 ID。这将确保原本的内容被 1:1 还原到 PPT 中。
4. 如果有表格数据但没有图片碎片，请在 `table` 字段填入 Markdown 格式的表格。
5. 为每页选择合适的 `layout_type`（text_only / text_image / full_image / two_column / diagram）。
"""

        return f"""以下是需要处理的文档：
{docs_text}

要求：
- 生成不超过 {max_slides} 个章节。
{common}
- 模式：{mode} (summarize=总结提取, convert=严格结构保持)。
- 只输出符合以下格式要求的JSON。不要输出额外的解释文字。

{format_instr}
"""
