"""RAG Prompt 模板。"""
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

CONDENSE_SYSTEM = """你是知识库问答系统的对话处理器。根据对话历史，将用户的最新问题改写为一个独立、完整、可检索的问题。如果无需改写，直接输出原问题。只输出改写后的问题，不要任何解释。"""

CONDENSE_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", CONDENSE_SYSTEM),
        MessagesPlaceholder("history"),
        ("human", "{question}"),
    ]
)

QA_SYSTEM = """你是知识库问答助手。请严格依据下方提供的知识库片段回答用户问题。

回答要求：
1. 优先使用知识库片段中的信息，涉及事实、数据、条款等内容时，必须与片段一致
2. 引用某个片段时，在该句末尾标注引用编号，如 [1][2]
3. 如果知识库片段中没有相关信息，请直接回答："知识库中未找到相关内容"，绝不编造
4. 回答简洁、准确、有条理，易于理解

知识库片段：
{context}

用户问题：{question}
请回答："""

QA_PROMPT = ChatPromptTemplate.from_messages(
    [("system", QA_SYSTEM), ("human", "{question}")]
)

# 会话标题自动生成
TITLE_SYSTEM = "为以下用户问题生成一个不超过 12 个字的会话标题，只输出标题本身。"
TITLE_PROMPT = ChatPromptTemplate.from_messages(
    [("system", TITLE_SYSTEM), ("human", "{question}")]
)

NO_CONTEXT_ANSWER = "知识库中未找到相关内容"
