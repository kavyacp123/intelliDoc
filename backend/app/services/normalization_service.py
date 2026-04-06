import re
from typing import Dict, List, Any, Optional

class NormalizationService:
    """
    Data normalization layer that maps unknown fields into standard business concepts.
    """
    
    # Standard concepts and their keyword mappings
    CONCEPT_MAPPING = {
        "revenue": ["revenue", "sales", "earnings", "income", "turnover", "gross_sales", "net_sales"],
        "cogs": ["cogs", "cost_of_goods_sold", "direct_costs", "cost_of_sales", "material_costs"],
        "opex_sales": ["sales_expense", "selling_costs", "advertising", "promotions"],
        "opex_marketing": ["marketing", "ad_spend", "brand_expense", "market_research"],
        "opex_ga": ["general_and_administrative", "admin", "rent", "salaries", "utilities", "office_costs"],
        "opex": ["opex", "operating_expense", "indirect_costs", "overhead"],
        "interest": ["interest", "finance_costs", "borrowing_costs"],
        "tax": ["tax", "income_tax", "vat", "gst", "corporate_tax"],
        "other_income": ["other_income", "interest_earned", "investment_income"],
        "other_expenses": ["other_expenses", "miscellaneous", "fines", "penalties"],
        "time": ["date", "time", "month", "year", "quarter", "timestamp", "period", "fiscal_year"],
        "category": ["category", "segment", "product", "region", "country", "industry", "type"],
        "target": ["target", "budget", "forecast", "goal", "expected"]
    }

    @classmethod
    def normalize_schema(cls, sample_data: List[Dict[str, Any]]) -> Dict[str, str]:
        """
        Detects field mappings based on the first row of data.
        Returns a mapping of {original_field: standard_concept}.
        """
        if not sample_data:
            return {}
            
        first_row = sample_data[0]
        mapping = {}
        
        for field in first_row.keys():
            normalized_field = field.lower().replace(" ", "_")
            
            # Check for direct or keyword matches
            found = False
            for concept, keywords in cls.CONCEPT_MAPPING.items():
                if normalized_field in keywords or any(k in normalized_field for k in keywords):
                    mapping[field] = concept
                    found = True
                    break
            
            if not found:
                # Basic type detection if no keyword match
                val = first_row[field]
                if isinstance(val, (int, float)):
                    mapping[field] = "numeric"
                else:
                    mapping[field] = "categorical"
                    
        return mapping

    @classmethod
    def apply_normalization(cls, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Transforms a dataset into a normalized format where keys are standard concepts.
        """
        schema_map = cls.normalize_schema(data)
        normalized_data = []
        
        for row in data:
            new_row = {}
            for field, concept in schema_map.items():
                # If multiple fields map to the same concept (rare), the last one wins
                # or we could aggregate them. For now, simple mapping.
                new_row[concept] = row[field]
            normalized_data.append(new_row)
            
        return normalized_data
