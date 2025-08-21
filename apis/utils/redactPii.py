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
            logger.info("Successfully loaded spaCy model 'en_core_web_sm' for Named Entity Recognition")
        except OSError:
            logger.warning("spaCy model 'en_core_web_sm' not found. Using basic English tokenizer. Named entity recognition will be limited.")
            try:
                self.nlp = spacy.load("en_core_web_md")
                logger.info("Successfully loaded spaCy model 'en_core_web_md'")
            except OSError:
                try:
                    self.nlp = spacy.load("en_core_web_lg")
                    logger.info("Successfully loaded spaCy model 'en_core_web_lg'")
                except OSError:
                    self.nlp = English()
                    logger.warning("No spaCy models found. Name detection will be limited.")
        
        self.redaction_patterns = self._compile_patterns()
        
        # Common first names for additional validation
        self.common_first_names = {
            'james', 'robert', 'john', 'michael', 'david', 'william', 'richard', 'charles', 'joseph', 'thomas',
            'christopher', 'daniel', 'paul', 'mark', 'donald', 'george', 'kenneth', 'steven', 'edward', 'brian',
            'ronald', 'anthony', 'kevin', 'jason', 'matthew', 'gary', 'timothy', 'jose', 'larry', 'jeffrey',
            'frank', 'scott', 'eric', 'stephen', 'andrew', 'raymond', 'gregory', 'joshua', 'jerry', 'dennis',
            'walter', 'patrick', 'peter', 'harold', 'douglas', 'henry', 'carl', 'arthur', 'ryan', 'roger',
            'mary', 'patricia', 'linda', 'barbara', 'elizabeth', 'jennifer', 'maria', 'susan', 'margaret', 'dorothy',
            'lisa', 'nancy', 'karen', 'betty', 'helen', 'sandra', 'donna', 'carol', 'ruth', 'sharon',
            'michelle', 'laura', 'sarah', 'kimberly', 'deborah', 'jessica', 'shirley', 'cynthia', 'angela', 'melissa',
            'brenda', 'emma', 'olivia', 'ava', 'sophia', 'isabella', 'charlotte', 'amelia', 'mia', 'harper',
            'evelyn', 'abigail', 'emily', 'ella', 'elizabeth', 'camila', 'luna', 'sofia', 'avery', 'mila',
            # Common South African names
            'sipho', 'thabo', 'nomsa', 'precious', 'blessing', 'gift', 'mercy', 'grace', 'faith', 'hope',
            'justice', 'patience', 'prudence', 'happiness', 'joy', 'peace', 'love', 'lucky', 'bright', 'smart',
            'johannes', 'petrus', 'maria', 'anna', 'elizabeth', 'susanna', 'magdalena', 'catharina', 'sara',
            'tevin', 'jim', 'jane', 'sarah', 'michael', 'patterson', 'robinson', 'doe', 'johnson', 'connor',
            'watson', 'smith'
        }
        
        # Words that should NOT be considered names
        self.false_positive_names = {
            'street', 'avenue', 'road', 'drive', 'lane', 'court', 'place', 'boulevard',
            'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday',
            'january', 'february', 'march', 'april', 'may', 'june', 'july', 'august',
            'september', 'october', 'november', 'december', 'jan', 'feb', 'mar', 'apr',
            'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec',
            'company', 'corporation', 'limited', 'bank', 'insurance', 'group',
            'services', 'department', 'office', 'center', 'centre', 'university',
            'college', 'school', 'hospital', 'clinic', 'pharmacy', 'store',
            'hello', 'dear', 'sincerely', 'regards', 'thank', 'thanks', 'please',
            'policy', 'account', 'number', 'contact', 'phone', 'email', 'address',
            'johannesburg', 'cape', 'town', 'durban', 'pretoria', 'bloemfontein',
            'port', 'elizabeth', 'kimberley', 'polokwane', 'nelspruit', 'mahikeng',
            'south', 'africa', 'african', 'america', 'american', 'europe', 'european',
            'asia', 'asian', 'australia', 'australian', 'canada', 'canadian',
            'england', 'english', 'france', 'french', 'germany', 'german',
            'today', 'tomorrow', 'yesterday', 'morning', 'afternoon', 'evening',
            'night', 'time', 'date', 'year', 'month', 'week', 'day', 'hour',
            'minute', 'second', 'am', 'pm', 'good', 'bad', 'best', 'worst',
            'first', 'last', 'next', 'previous', 'new', 'old', 'young', 'age',
            'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'from', 'up', 'about', 'into', 'over', 'after'
        }
        
    def _compile_patterns(self) -> dict:
        patterns = {
            'sa_id': re.compile(r'\b\d{13}\b'),
            
            'sa_phone': re.compile(
                r'(?:\+27[\s-]?(?:\d{2}[\s-]?\d{3}[\s-]?\d{4}|\d{1}[\s-]?\d{3}[\s-]?\d{4}|\d{3}[\s-]?\d{6}))|'
                r'(?:\+44[\s-]?\d{2,4}[\s-]?\d{3,4}[\s-]?\d{4})|'
                r'(?:(?:0(?:11|12|13|14|15|16|17|18|21|22|23|27|28|31|32|33|34|35|36|37|38|39|40|41|42|43|44|45|46|47|48|49|51|53|54|56|57|58|82|83|84|86|87))[\s-]?\d{3}[\s-]?\d{4})|'
                r'(?:0\d{2}[\s-]?\d{3}[\s-]?\d{4})|'
                r'(?:0\d{2}[\s-]?\d{4}[\s-]?\d{3})|'
                r'(?:0\d{3}[\s-]?\d{3}[\s-]?\d{3})|'
                r'(?:\b0\d{9}\b)',
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
    
    def _is_likely_name(self, text: str) -> bool:
        """
        Enhanced name validation using multiple heuristics
        """
        text_lower = text.lower().strip()
        words = text_lower.split()
        
        # Skip if in false positive list
        if text_lower in self.false_positive_names:
            return False
        
        # Skip if any word is in false positives
        if any(word in self.false_positive_names for word in words):
            return False
        
        # Skip if contains numbers
        if re.search(r'\d', text):
            return False
        
        # Skip if too short
        if len(text.replace(' ', '')) < 2:
            return False
        
        # Skip if all punctuation
        if re.match(r'^[^\w]+$', text):
            return False
        
        # Must have at least 2 words for full names
        if len(words) < 2:
            return False
        
        # Check if any word is a known first name
        has_known_name = any(word in self.common_first_names for word in words)
        
        # Check if it follows name patterns
        follows_pattern = False
        
        # Pattern 1: At least one word starts with capital letter
        if any(word[0].isupper() for word in text.split() if word):
            follows_pattern = True
        
        # Pattern 2: Common name length (2-4 words, each 2-15 chars)
        if 2 <= len(words) <= 4 and all(2 <= len(word) <= 15 for word in words):
            follows_pattern = True
        
        # Pattern 3: Contains common name suffixes
        name_suffixes = ['son', 'sen', 'ing', 'er', 'man', 'ton', 'ley', 'field']
        if any(words[-1].endswith(suffix) for suffix in name_suffixes):
            follows_pattern = True
        
        # More likely to be a name if it has known names OR follows patterns
        return has_known_name or follows_pattern
    
    def _get_named_entities(self, text: str) -> List[Tuple[str, int, int]]:
        """
        Get named entities using spaCy NER
        """
        entities = []
        try:
            doc = self.nlp(text)
            for ent in doc.ents:
                if ent.label_ == 'PERSON':
                    if self._is_likely_name(ent.text):
                        entities.append((ent.text, ent.start_char, ent.end_char))
                        logger.debug(f"NER detected person name: '{ent.text}'")
                        
        except Exception as e:
            logger.warning(f"Error extracting named entities: {e}")
        
        return entities
    
    def _find_names_with_patterns(self, text: str) -> List[Tuple[int, int, str]]:
        """
        Comprehensive regex-based name detection with multiple patterns
        """
        matches = []
        
        # Enhanced patterns for name detection
        name_patterns = [
            # Names with titles
            re.compile(r'\b(?:Mr\.?|Mrs\.?|Ms\.?|Miss\.?|Dr\.?|Prof\.?|Professor\.?)\s+[A-Za-z\'\-]+(?:\s+[A-Za-z\'\-]+)*\b', re.IGNORECASE),
            
            # Standard capitalized names (John Smith)
            re.compile(r'\b[A-Z][a-z\'\-]{1,}\s+[A-Z][a-z\'\-]{1,}(?:\s+[A-Z][a-z\'\-]{1,})?\b'),
            
            # Mixed case (john Smith, JOHN smith, etc.)
            re.compile(r'\b[a-zA-Z][a-z\'\-]{1,}\s+[A-Z][a-z\'\-]{1,}(?:\s+[A-Z][a-z\'\-]{1,})?\b'),
            re.compile(r'\b[A-Z][a-z\'\-]{1,}\s+[a-z][a-z\'\-]{1,}(?:\s+[A-Z][a-z\'\-]{1,})?\b'),
            
            # All lowercase names (jim patterson)
            re.compile(r'\b[a-z]{2,}\s+[a-z]{2,}(?:\s+[a-z]{2,})?\b'),
            
            # All uppercase names
            re.compile(r'\b[A-Z]{2,}\s+[A-Z]{2,}(?:\s+[A-Z]{2,})?\b'),
            
            # Names with initials
            re.compile(r'\b[A-Z]\.?\s+[A-Z][a-z\'\-]+\b'),
            re.compile(r'\b[A-Z][a-z\'\-]+\s+[A-Z]\.?\b'),
            re.compile(r'\b[A-Z][a-z\'\-]*\s+[A-Z]\.?\s+[A-Z][a-z\'\-]+\b'),
            
            # Hyphenated names
            re.compile(r'\b[A-Za-z][a-z\'\-]*-[A-Za-z][a-z\'\-]*(?:\s+[A-Za-z][a-z\'\-]+)?\b'),
            
            # Names with apostrophes (O'Connor, D'Angelo)
            re.compile(r'\b[A-Za-z]\'[A-Z][a-z]+(?:\s+[A-Z][a-z\'\-]+)?\b', re.IGNORECASE),
            
            # South African naming patterns
            re.compile(r'\b[A-Za-z][a-z\'\-]*\s+(?:van\s+der\s+[A-Za-z][a-z\'\-]+|van\s+[A-Za-z][a-z\'\-]+|de\s+[A-Za-z][a-z\'\-]+|du\s+[A-Za-z][a-z\'\-]+)\b', re.IGNORECASE),
        ]
        
        for pattern in name_patterns:
            for match in pattern.finditer(text):
                match_text = match.group().strip()
                if self._is_likely_name(match_text):
                    matches.append((match.start(), match.end(), 'pattern_name'))
                    logger.debug(f"Pattern detected name: '{match_text}'")
        
        return matches
    
    def _find_all_matches(self, text: str) -> List[Tuple[int, int, str]]:
        matches = []
        
        # Process standard PII patterns first
        for pattern_name, pattern in self.redaction_patterns.items():
            for match in pattern.finditer(text):
                matches.append((match.start(), match.end(), pattern_name))
        
        # Get NER-based names
        entities = self._get_named_entities(text)
        for entity_text, start, end in entities:
            matches.append((start, end, 'ner_name'))
        
        # Get pattern-based names (always run for comprehensive coverage)
        pattern_matches = self._find_names_with_patterns(text)
        matches.extend(pattern_matches)
        
        # Sort matches by start position
        matches.sort(key=lambda x: x[0])
        
        # Merge overlapping matches, preferring longer matches
        merged_matches = []
        for start, end, match_type in matches:
            if merged_matches and start <= merged_matches[-1][1]:
                prev_start, prev_end, prev_type = merged_matches[-1]
                # Keep the longer match, or prefer NER over pattern matches
                if (end - start) > (prev_end - prev_start) or 'ner' in match_type:
                    merged_matches[-1] = (min(start, prev_start), max(end, prev_end), match_type)
                else:
                    merged_matches[-1] = (prev_start, max(end, prev_end), prev_type)
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
            
            logger.info(f"Redacted {len(matches)} PII items from text using enhanced name detection")
            
            return redacted_text
            
        except Exception as e:
            logger.error(f"Error during PII redaction: {e}")
            return text


def redact_pii(text: str) -> str:
    service = RedactPiiService()
    return service.redact(text)


if __name__ == "__main__":
    test_text = """
    Hello, tevin richard here and jim patterson will call you. I live at 123 Main Street, Johannesburg 2000.
    My phone number is +27 82 123 4567 or you can reach me at 011-234-5678 or even 0747584931 or 074 758 4931.
    My ID is 9901015080084 and my passport is A12345678.
    My policy number is 123456789 and my bank account is 1234567890123456.
    You can email me at john.smith@example.com.
    I work with Jane Doe and mary jane watson at ABC Corporation in Cape Town.
    Dr. Sarah Johnson and Prof. Michael O'Connor will attend the meeting.
    """
    
    redacted = redact_pii(test_text)
    print("Original text:")
    print(test_text)
    print("\nRedacted text:")
    print(redacted)