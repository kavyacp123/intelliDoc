"""
AI Query Suggestion Service.

Generates 3 clarified, schema-aware query suggestions when the user
types an ambiguous or short question. Uses Groq LLM with the dataset's
actual column names and types to produce relevant suggestions.
"""

import json
import re
import logging
from typing import List, Optional

from groq import Groq
from app.core.config import settings
from app.models.metadata import TableMetadata

logger = logging.getLogger(__name__)


def is_completely_vague(question: str) -> bool:
    """Return True when a query is too broad to execute meaningfully."""
    vague_inputs = {
        "show data",
        "show me data",
        "show summary",
        "summary",
        "overview",
        "performance",
        "show performance",
    }
    return question.lower().strip() in vague_inputs


def generate_suggestions(
    question: str,
    schemas: List[TableMetadata],
    max_suggestions: int = 3,
) -> List[str]:
    """
    Generate clarified query suggestions based on the user's question
    and the dataset's actual schema.

    Args:
        question: The user's original (possibly vague) query.
        schemas: List of TableMetadata for the active dataset.
        max_suggestions: Number of suggestions to generate.

    Returns:
        A list of natural-language query suggestions.
    """
    if not settings.GROQ_API_KEY:
        return []

    # Build column context from schema
    all_columns = []
    numeric_columns = []
    text_columns = []
    time_columns = []

    for s in schemas:
        for c in s.columns:
            all_columns.append(f"{c.name} ({c.dtype})")
            if c.dtype.lower() in ("int", "float", "double", "bigint", "integer"):
                numeric_columns.append(c.name)
            elif c.dtype.lower() in ("datetime", "date", "timestamp"):
                time_columns.append(c.name)
            else:
                text_columns.append(c.name)

    system_prompt = """You are a data analytics assistant.
The user typed a vague or short query about their dataset.
Your job is to suggest 3 clear, specific analytical questions they might be asking.

Rules:
* Use ONLY the column names provided — never invent columns
* Each suggestion must be a complete, natural-language question
* Suggestions should cover different analytical angles (e.g., aggregation, trend, comparison)
* Keep suggestions concise (under 15 words each)
* Return ONLY a JSON array of strings, nothing else

Example output:
["Total revenue by region", "Monthly sales trend over time", "Top 5 products by profit"]"""

    user_prompt = f"""Dataset columns:
Numeric (for metrics): {', '.join(numeric_columns) if numeric_columns else 'none'}
Text (for dimensions): {', '.join(text_columns) if text_columns else 'none'}
Time (for trends): {', '.join(time_columns) if time_columns else 'none'}

User's query: "{question}"

Generate {max_suggestions} specific suggestions as a JSON array:"""

    try:
        client = Groq(api_key=settings.GROQ_API_KEY)
        response = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            response_format={"type": "json_object"},
        )

        raw = response.choices[0].message.content.strip()

        # Strip markdown fences if present
        raw = re.sub(r"^```[a-zA-Z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
        raw = raw.strip()

        parsed = json.loads(raw)

        # Handle both {"suggestions": [...]} and direct [...] formats
        if isinstance(parsed, list):
            suggestions = parsed
        elif isinstance(parsed, dict):
            # Try common keys
            for key in ["suggestions", "queries", "questions", "result"]:
                if key in parsed and isinstance(parsed[key], list):
                    suggestions = parsed[key]
                    break
            else:
                # Take the first list value found
                for v in parsed.values():
                    if isinstance(v, list):
                        suggestions = v
                        break
                else:
                    suggestions = []
        else:
            suggestions = []

        # Ensure all items are strings and limit count
        suggestions = [str(s) for s in suggestions if s][:max_suggestions]

        logger.info("Generated %d suggestions for query: '%s'", len(suggestions), question)
        return suggestions

    except Exception as e:
        logger.warning("Suggestion generation failed: %s", e)
        return []
