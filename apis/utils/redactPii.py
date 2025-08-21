import re
import logging
from typing import List, Tuple, Optional
import spacy
from spacy.lang.en import English

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RedactPiiService:
    def __init__(self):
        try:
            self.nlp = spacy.load("en_core_web_sm")
        except OSError:
            logger.warning("spaCy model 'en_core_web_sm' not found. Using basic English tokenizer. Named entity recognition will be limited.")
            self.nlp = English()
        
        self.redaction_patterns = self._compile_patterns()
        
    def _compile_patterns(self) -> dict:
        patterns = {
            'sa_id': re.compile(r'\b\d{13}\b'),
            
            'sa_phone': re.compile(
                r'\+27\s?\d{1,2}\s?\d{3}\s?\d{4}|'
                r'\+44\s?\d{2,4}\s?\d{3,4}\s?\d{4}|'
                r'(?:011|012|013|014|015|016|017|018|021|022|023|027|028|031|032|033|034|035|036|037|038|039|040|041|042|043|044|045|046|047|048|049|051|053|054|056|057|058|082|083|084|086|087)[\s-]?\d{3}[\s-]?\d{4}|'
                r'\b0\d{9}\b',
                re.IGNORECASE
            ),
            
            'policy_number': re.compile(r'\b\d{9}\b'),
            
            'passport': re.compile(
                r'\b[A-Z]{1,2}\d{6,9}\b|'
                r'\b[A-Z]\d{7,8}\b',
                re.IGNORECASE
            ),
            
            'bank_account': re.compile(
                r'\b\d{6,17}\b|'
                r'\bIBAN[\s:]?[A-Z]{2}\d{2}[A-Z0-9]{4}\d{7}([A-Z0-9]?){0,16}\b|'
                r'\b[A-Z]{2}\d{2}[A-Z0-9]{4}\d{7}([A-Z0-9]?){0,16}\b',
                re.IGNORECASE
            ),
            
            'credit_card': re.compile(
                r'\b(?:4[0-9]{12}(?:[0-9]{3})?|'
                r'5[1-5][0-9]{14}|'
                r'3[47][0-9]{13}|'
                r'3(?:0[0-5]|[68][0-9])[0-9]{11}|'
                r'6(?:011|5[0-9]{2})[0-9]{12}|'
                r'(?:2131|1800|35\d{3})\d{11})\b'
            ),
            
            'email': re.compile(
                r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
                re.IGNORECASE
            ),
            
            'postal_address': re.compile(
                r'(?:P\.?O\.?\s?Box\s?\d+|'
                r'\d+\s+[\w\s]+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr|Court|Ct|Circle|Cir|Plaza|Pl|Place)[\s,]*'
                r'(?:[\w\s]+,\s*)?(?:[A-Z]{2}\s+)?\d{4,5})',
                re.IGNORECASE | re.MULTILINE
            ),
            
            'street_address': re.compile(
                r'\b\d+\s+(?:[A-Z][a-z]+\s+){1,4}(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr|Court|Ct|Circle|Cir|Plaza|Pl|Place)\b',
                re.IGNORECASE
            )
        }
        return patterns
    
    def _normalize_text(self, text: str) -> str:
        return re.sub(r'\s+', ' ', text)
    
    def _get_named_entities(self, text: str) -> List[Tuple[str, int, int]]:
        entities = []
        try:
            doc = self.nlp(text)
            for ent in doc.ents:
                if ent.label_ in ['PERSON', 'ORG', 'GPE', 'LOC', 'FAC']:
                    entities.append((ent.text, ent.start_char, ent.end_char))
        except Exception as e:
            logger.warning(f"Error extracting named entities: {e}")
        return entities
    
    def _find_all_matches(self, text: str) -> List[Tuple[int, int, str]]:
        matches = []
        
        normalized_text = self._normalize_text(text)
        
        for pattern_name, pattern in self.redaction_patterns.items():
            for match in pattern.finditer(text):
                matches.append((match.start(), match.end(), pattern_name))
        
        entities = self._get_named_entities(text)
        for entity_text, start, end in entities:
            matches.append((start, end, 'named_entity'))
        
        customer_name_patterns = [
            re.compile(r'\b(?:Mr\.?|Mrs\.?|Ms\.?|Dr\.?|Prof\.?)\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b'),
            re.compile(r'\b[A-Z][a-z]+\s+(?:[A-Z]\.?\s+)?[A-Z][a-z]+\b'),
        ]
        
        for pattern in customer_name_patterns:
            for match in pattern.finditer(text):
                if not any(kw in match.group().lower() for kw in ['street', 'avenue', 'road', 'drive', 'lane', 'court', 'place', 'boulevard']):
                    matches.append((match.start(), match.end(), 'customer_name'))
        
        matches.sort(key=lambda x: x[0])
        
        merged_matches = []
        for start, end, match_type in matches:
            if merged_matches and start <= merged_matches[-1][1]:
                merged_matches[-1] = (merged_matches[-1][0], max(end, merged_matches[-1][1]), merged_matches[-1][2])
            else:
                merged_matches.append((start, end, match_type))
        
        return merged_matches
    
    def redact(self, text: str) -> str:
        if not text:
            return text
        
        try:
            matches = self._find_all_matches(text)
            
            if not matches:
                return text
            
            result = []
            last_end = 0
            
            for start, end, match_type in matches:
                result.append(text[last_end:start])
                result.append('[REDACTED]')
                last_end = end
            
            result.append(text[last_end:])
            
            redacted_text = ''.join(result)
            
            logger.info(f"Redacted {len(matches)} PII items from text")
            
            return redacted_text
            
        except Exception as e:
            logger.error(f"Error during PII redaction: {e}")
            return text


def redact_pii(text: str) -> str:
    service = RedactPiiService()
    return service.redact(text)


if __name__ == "__main__":
    test_text = """
    Hello, my name is John Smith and I live at 123 Main Street, Johannesburg 2000.
    My phone number is +27 82 123 4567 or you can reach me at 011-234-5678.
    My ID number is 9901015080084 and my passport is A12345678.
    My policy number is 123456789 and my bank account is 1234567890123456.
    You can email me at john.smith@example.com.
    I work with Jane Doe at ABC Corporation in Cape Town.
    """
    
    redacted = redact_pii(test_text)
    print("Original text:")
    print(test_text)
    print("\nRedacted text:")
    print(redacted)