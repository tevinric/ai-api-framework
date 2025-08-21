import re
import logging
from typing import List, Tuple, Optional, Dict, Set
import spacy
from spacy.lang.en import English
from collections import defaultdict
import string

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
        
        # Enhanced first names database with weighted scoring
        self.common_first_names = self._build_name_database()
        self.common_surnames = self._build_surname_database()
        
        # South African specific names
        self.sa_names = {
            # African names
            'sipho', 'thabo', 'nomsa', 'precious', 'blessing', 'gift', 'mercy', 'grace', 'faith', 'hope',
            'justice', 'patience', 'prudence', 'happiness', 'joy', 'peace', 'love', 'lucky', 'bright', 'smart',
            'mandla', 'bongani', 'sibusiso', 'nkosana', 'themba', 'mpho', 'lerato', 'thandeka', 'zanele', 'nokuthula',
            'kagiso', 'tshepo', 'lebo', 'palesa', 'dineo', 'kgomotso', 'lesego', 'tebogo', 'ntombi', 'busisiwe',
            # Afrikaans names  
            'johannes', 'petrus', 'jacobus', 'hendrik', 'pieter', 'francois', 'adriaan', 'andries', 'willem', 'gert',
            'anna', 'maria', 'susanna', 'magdalena', 'catharina', 'sara', 'elizabeth', 'aletta', 'martha', 'helena',
            'jan', 'koos', 'piet', 'fanie', 'hennie', 'kobus', 'danie', 'johan', 'jaco', 'christo'
        }
        
        # Name context indicators
        self.name_context_words = {
            'before': {'hello', 'hi', 'dear', 'mr', 'mrs', 'ms', 'miss', 'dr', 'prof', 'professor', 'sir', 'madam',
                      'contact', 'customer', 'client', 'patient', 'student', 'employee', 'manager', 'director',
                      'ceo', 'cfo', 'cto', 'owner', 'founder', 'representative', 'agent', 'officer'},
            'after': {'said', 'says', 'stated', 'mentioned', 'called', 'phoned', 'emailed', 'contacted', 'visited',
                     'signed', 'approved', 'rejected', 'submitted', 'filed', 'registered', 'enrolled'}
        }
        
        # Security keywords that should trigger redaction of following values
        self.security_keywords = {
            'password', 'passwd', 'pwd', 'pass', 'secret', 'token', 'key', 'apikey', 'api_key',
            'client_secret', 'client_id', 'access_token', 'refresh_token', 'bearer',
            'authorization', 'auth', 'credential', 'private_key', 'public_key',
            'ssh', 'rsa', 'dsa', 'ecdsa', 'ed25519', 'pgp', 'gpg',
            'aws_access_key_id', 'aws_secret_access_key', 'azure_api_key',
            'google_api_key', 'github_token', 'gitlab_token', 'slack_token',
            'stripe_key', 'sendgrid_key', 'twilio_key', 'mailgun_key'
        }
        
        # Enhanced false positive detection
        self.false_positive_names = {
            # Location indicators
            'street', 'avenue', 'road', 'drive', 'lane', 'court', 'place', 'boulevard', 'highway', 'parkway',
            'circle', 'square', 'plaza', 'terrace', 'trail', 'way', 'alley', 'crescent', 'grove', 'park',
            # Time related
            'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday',
            'january', 'february', 'march', 'april', 'may', 'june', 'july', 'august',
            'september', 'october', 'november', 'december', 'jan', 'feb', 'mar', 'apr',
            'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec',
            'today', 'tomorrow', 'yesterday', 'morning', 'afternoon', 'evening', 'night',
            # Business entities
            'company', 'corporation', 'limited', 'ltd', 'llc', 'inc', 'plc', 'pty', 'proprietary',
            'bank', 'insurance', 'group', 'holdings', 'enterprises', 'solutions', 'consulting',
            'services', 'department', 'office', 'center', 'centre', 'university',
            'college', 'school', 'hospital', 'clinic', 'pharmacy', 'store', 'shop',
            # SA specific business
            'absa', 'fnb', 'nedbank', 'capitec', 'standardbank', 'discovery', 'sanlam', 'oldmutual',
            'vodacom', 'mtn', 'telkom', 'cell', 'sasol', 'eskom', 'transnet', 'sars',
            # Common words
            'hello', 'dear', 'sincerely', 'regards', 'thank', 'thanks', 'please', 'kindly',
            'policy', 'account', 'number', 'contact', 'phone', 'email', 'address', 'reference',
            'payment', 'transaction', 'transfer', 'deposit', 'withdrawal', 'balance', 'statement',
            # SA cities and places
            'johannesburg', 'joburg', 'cape', 'town', 'durban', 'pretoria', 'tshwane', 'bloemfontein',
            'port', 'elizabeth', 'gqeberha', 'kimberley', 'polokwane', 'nelspruit', 'mbombela', 'mahikeng',
            'sandton', 'rosebank', 'midrand', 'centurion', 'soweto', 'randburg', 'fourways', 'bedfordview',
            # Countries and nationalities
            'south', 'africa', 'african', 'america', 'american', 'europe', 'european',
            'asia', 'asian', 'australia', 'australian', 'canada', 'canadian',
            'england', 'english', 'france', 'french', 'germany', 'german', 'china', 'chinese',
            # Common English words
            'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'from', 'up', 'about', 'into', 'over', 'after',
            'this', 'that', 'these', 'those', 'what', 'which', 'who', 'whom', 'whose', 'where', 'when', 'why', 'how',
            'all', 'any', 'both', 'each', 'few', 'more', 'most', 'other', 'some', 'such', 'only', 'own', 'same',
            'so', 'than', 'too', 'very', 'can', 'will', 'just', 'should', 'now'
        }
        
    def _build_name_database(self) -> Set[str]:
        """Build comprehensive first names database"""
        return {
            # English names
            'james', 'robert', 'john', 'michael', 'david', 'william', 'richard', 'charles', 'joseph', 'thomas',
            'christopher', 'daniel', 'paul', 'mark', 'donald', 'george', 'kenneth', 'steven', 'edward', 'brian',
            'ronald', 'anthony', 'kevin', 'jason', 'matthew', 'gary', 'timothy', 'jose', 'larry', 'jeffrey',
            'frank', 'scott', 'eric', 'stephen', 'andrew', 'raymond', 'gregory', 'joshua', 'jerry', 'dennis',
            'walter', 'patrick', 'peter', 'harold', 'douglas', 'henry', 'carl', 'arthur', 'ryan', 'roger',
            'joe', 'juan', 'jack', 'albert', 'jonathan', 'justin', 'terry', 'gerald', 'keith', 'samuel',
            'willie', 'ralph', 'lawrence', 'nicholas', 'roy', 'benjamin', 'bruce', 'brandon', 'adam', 'nathan',
            'mary', 'patricia', 'linda', 'barbara', 'elizabeth', 'jennifer', 'maria', 'susan', 'margaret', 'dorothy',
            'lisa', 'nancy', 'karen', 'betty', 'helen', 'sandra', 'donna', 'carol', 'ruth', 'sharon',
            'michelle', 'laura', 'sarah', 'kimberly', 'deborah', 'jessica', 'shirley', 'cynthia', 'angela', 'melissa',
            'brenda', 'emma', 'olivia', 'ava', 'sophia', 'isabella', 'charlotte', 'amelia', 'mia', 'harper',
            'evelyn', 'abigail', 'emily', 'ella', 'elizabeth', 'camila', 'luna', 'sofia', 'avery', 'mila',
            'amy', 'anna', 'rebecca', 'virginia', 'kathleen', 'pamela', 'martha', 'debra', 'amanda', 'stephanie',
            'carolyn', 'christine', 'marie', 'janet', 'catherine', 'frances', 'christina', 'samantha', 'nicole', 'judy',
            # Common nicknames
            'jim', 'bob', 'bill', 'mike', 'dave', 'dick', 'rick', 'charlie', 'joe', 'tom',
            'chris', 'dan', 'matt', 'greg', 'josh', 'andy', 'nick', 'ben', 'sam', 'alex',
            'liz', 'beth', 'jen', 'sue', 'maggie', 'kate', 'sally', 'annie', 'katie', 'becky',
            # Additional common names
            'tevin', 'trevor', 'tyler', 'taylor', 'travis', 'troy', 'todd', 'tommy', 'tony', 'tim'
        }
    
    def _build_surname_database(self) -> Set[str]:
        """Build comprehensive surnames database"""
        return {
            # Common English surnames
            'smith', 'johnson', 'williams', 'brown', 'jones', 'garcia', 'miller', 'davis', 'rodriguez', 'martinez',
            'hernandez', 'lopez', 'gonzalez', 'wilson', 'anderson', 'thomas', 'taylor', 'moore', 'jackson', 'martin',
            'lee', 'perez', 'thompson', 'white', 'harris', 'sanchez', 'clark', 'ramirez', 'lewis', 'robinson',
            'walker', 'young', 'allen', 'king', 'wright', 'scott', 'torres', 'nguyen', 'hill', 'flores',
            'green', 'adams', 'nelson', 'baker', 'hall', 'rivera', 'campbell', 'mitchell', 'carter', 'roberts',
            'patterson', 'connor', 'watson', 'murphy', 'cox', 'howard', 'ward', 'torres', 'peterson', 'gray',
            'ross', 'foster', 'butler', 'barnes', 'russell', 'griffin', 'hayes', 'coleman', 'jenkins', 'perry',
            # South African surnames
            'naidoo', 'pillay', 'govender', 'reddy', 'moodley', 'singh', 'khan', 'patel', 'naicker', 'chetty',
            'dlamini', 'zulu', 'ndlovu', 'sithole', 'nkosi', 'khumalo', 'mokoena', 'molefe', 'mthembu', 'ngcobo',
            'van der merwe', 'botha', 'pretorius', 'van wyk', 'kruger', 'nel', 'fourie', 'smit', 'venter', 'janse van rensburg',
            'visser', 'du plessis', 'meyer', 'erasmus', 'jacobs', 'hendriks', 'williams', 'adams', 'daniels', 'abrahams',
            'doe', 'roe', 'public', 'test', 'sample', 'example'
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
                r'(?:\b0\d{9}\b)|'
                r'(?:\(\d{3}\)[\s-]?\d{3}[\s-]?\d{4})|'  # (011) 123-4567 format
                r'(?:\b\d{3}[\s\.-]\d{3}[\s\.-]\d{4}\b)',  # 011.123.4567 or 011 123 4567
                re.IGNORECASE
            ),
            
            'policy_number': re.compile(r'\b\d{9}\b'),
            
            'passport': re.compile(
                r'\b[A-Z]{1,2}\d{6,9}\b|'
                r'\b[A-Z]\d{7,8}\b',
                re.IGNORECASE
            ),
            
            # South African bank account patterns
            'sa_bank_account': re.compile(
                r'\b(?:account[\s:#]*)?\d{9,11}\b|'  # Standard SA bank accounts
                r'\b\d{6}[\s-]?\d{5,7}\b|'  # Account with branch code
                r'\b(?:acc[\s:#]*)?\d{10,16}\b',  # Generic account numbers
                re.IGNORECASE
            ),
            
            # SA Bank branch codes
            'sa_branch_code': re.compile(
                r'\b(?:branch[\s:#]*)?(?:25[0-8]\d{3}|'  # Standard Bank
                r'47[0-9]\d{3}|'  # Capitec
                r'19[0-8]\d{3}|'  # Nedbank
                r'05[0-9]\d{3}|'  # ABSA
                r'25[0-9]\d{3}|'  # FNB
                r'\d{6})\b',  # Generic 6-digit
                re.IGNORECASE
            ),
            
            # Universal branch codes
            'universal_branch': re.compile(
                r'\b(?:051001|250655|470010|198765|632005)\b'  # Common universal codes
            ),
            
            # SWIFT/BIC codes for SA banks
            'swift_code': re.compile(
                r'\b(?:SBZA|ABSA|FIRNZAJJ|NEDSZAJJ|CABLZAJJ|ZARSZAJJ)[A-Z0-9]{0,3}\b',
                re.IGNORECASE
            ),
            
            # International bank accounts including IBAN
            'intl_bank_account': re.compile(
                r'\bIBAN[\s:]?[A-Z]{2}\d{2}[A-Z0-9]{4}\d{7}([A-Z0-9]?){0,16}\b|'
                r'\b[A-Z]{2}\d{2}[A-Z0-9]{4}\d{7}([A-Z0-9]?){0,16}\b',
                re.IGNORECASE
            ),
            
            'credit_card': re.compile(
                r'\b(?:4[0-9]{12}(?:[0-9]{3})?|'  # Visa
                r'5[1-5][0-9]{14}|'  # MasterCard
                r'3[47][0-9]{13}|'  # American Express
                r'3(?:0[0-5]|[68][0-9])[0-9]{11}|'  # Diners Club
                r'6(?:011|5[0-9]{2})[0-9]{12}|'  # Discover
                r'(?:2131|1800|35\d{3})\d{11})\b'  # JCB
            ),
            
            # CVV/CVC codes
            'cvv': re.compile(
                r'\b(?:cvv|cvc|cvv2|cvc2|security[\s]?code)[\s:#]*\d{3,4}\b',
                re.IGNORECASE
            ),
            
            # Transaction references and amounts
            'transaction_ref': re.compile(
                r'\b(?:ref(?:erence)?|trans(?:action)?|payment|receipt)[\s:#]*[A-Z0-9]{6,20}\b|'
                r'\b(?:TRN|REF|PAY|RCP)[0-9]{6,15}\b',
                re.IGNORECASE
            ),
            
            # Money amounts (SA Rand)
            'money_amount': re.compile(
                r'\bR[\s]?\d{1,3}(?:[,\s]?\d{3})*(?:\.\d{2})?\b|'  # R format
                r'\bZAR[\s]?\d{1,3}(?:[,\s]?\d{3})*(?:\.\d{2})?\b|'  # ZAR format
                r'\b(?:amount|balance|total)[\s:#]*\d{1,3}(?:[,\s]?\d{3})*(?:\.\d{2})?\b',
                re.IGNORECASE
            ),
            
            # SA VAT numbers
            'vat_number': re.compile(
                r'\b(?:vat[\s:#]*)?4\d{9}\b',
                re.IGNORECASE
            ),
            
            # Company registration numbers
            'company_reg': re.compile(
                r'\b(?:reg(?:istration)?[\s:#]*)?\d{4}\/\d{6}\/\d{2}\b|'
                r'\b(?:ck|cc)[\s]?\d{2}\/\d{4,6}\b',
                re.IGNORECASE
            ),
            
            'email': re.compile(
                r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
                re.IGNORECASE
            ),
            
            'postal_address': re.compile(
                r'(?:P\.?O\.?\s?Box\s?\d+|'
                r'(?:Private|Priv\.?)\s?Bag\s?[X]?\d+|'  # SA Private Bag
                r'Postnet\s?Suite\s?\d+|'  # Postnet addresses
                r'\d+\s+[\w\s]+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr|Court|Ct|Circle|Cir|Plaza|Pl|Place|Crescent|Cres|Close|Way)[\s,]*'
                r'(?:[\w\s]+,\s*)?(?:[A-Z]{2}\s+)?\d{4})',  # SA postcodes are 4 digits
                re.IGNORECASE | re.MULTILINE
            ),
            
            'street_address': re.compile(
                r'\b\d+\s+(?:[A-Z][a-z]+\s+){1,4}(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr|Court|Ct|Circle|Cir|Plaza|Pl|Place|Crescent|Cres|Close|Way)\b',
                re.IGNORECASE
            ),
            
            # SA postal codes
            'sa_postal_code': re.compile(
                r'\b(?:postal[\s]?code[\s:#]*)?\d{4}\b',
                re.IGNORECASE
            ),
            
            # ============= SECURITY PATTERNS =============
            
            # Password patterns
            'password': re.compile(
                r'(?:password|passwd|pwd|pass|passcode|pin)[\s:=]*[\S]+|'  # password: value
                r'(?:password|passwd|pwd|pass)\s*[=:]\s*["\'][^"^\']+["\']|'  # password="value"
                r'(?:password|passwd|pwd|pass)\s*[=:]\s*[^\s,;]+',  # password=value
                re.IGNORECASE
            ),
            
            # API Keys - Generic patterns
            'api_key_generic': re.compile(
                r'(?:api[_\s]?key|apikey|api[_\s]?token|api[_\s]?secret)[\s:=]*[A-Za-z0-9\-_]{20,}|'
                r'(?:key|token|secret)[\s:=]*[A-Za-z0-9\-_]{32,}',
                re.IGNORECASE
            ),
            
            # AWS Keys
            'aws_access_key': re.compile(
                r'(?:AKIA|A3T|AGPA|AIDA|AROA|AIPA|ANPA|ANVA|ASIA)[A-Z0-9]{16}|'  # AWS Access Key ID
                r'aws[_\s]?access[_\s]?key[_\s]?id[\s:=]*[A-Z0-9]{20}',
                re.IGNORECASE
            ),
            'aws_secret_key': re.compile(
                r'aws[_\s]?secret[_\s]?access[_\s]?key[\s:=]*[A-Za-z0-9/+=]{40}',
                re.IGNORECASE
            ),
            
            # Azure Keys
            'azure_key': re.compile(
                r'(?:azure[_\s]?(?:api[_\s]?key|subscription[_\s]?key|client[_\s]?secret))[\s:=]*[A-Za-z0-9\-_]{32,}|'
                r'DefaultEndpointsProtocol=https;AccountName=[^;]+;AccountKey=[^;]+;',
                re.IGNORECASE
            ),
            
            # Google/GCP Keys
            'google_api_key': re.compile(
                r'AIza[0-9A-Za-z\-_]{35}|'  # Google API Key
                r'(?:google[_\s]?api[_\s]?key|gcp[_\s]?key)[\s:=]*[A-Za-z0-9\-_]{32,}',
                re.IGNORECASE
            ),
            'google_oauth': re.compile(
                r'[0-9]+-[0-9A-Za-z_]{32}\.apps\.googleusercontent\.com'  # Google OAuth
            ),
            
            # GitHub/GitLab Tokens
            'github_token': re.compile(
                r'ghp_[A-Za-z0-9]{36}|'  # GitHub Personal Access Token
                r'gho_[A-Za-z0-9]{36}|'  # GitHub OAuth Token
                r'ghu_[A-Za-z0-9]{36}|'  # GitHub User Token
                r'ghs_[A-Za-z0-9]{36}|'  # GitHub Server Token
                r'ghr_[A-Za-z0-9]{36}',  # GitHub Refresh Token
                re.IGNORECASE
            ),
            'gitlab_token': re.compile(
                r'glpat-[A-Za-z0-9\-_]{20}|'  # GitLab Personal Access Token
                r'glptt-[A-Za-z0-9]{40}'  # GitLab Pipeline Trigger Token
            ),
            
            # Slack Tokens
            'slack_token': re.compile(
                r'xox[baprs]-[A-Za-z0-9]{10,48}|'  # Slack Tokens
                r'slack[_\s]?(?:api[_\s]?)?token[\s:=]*xox[baprs]-[A-Za-z0-9]{10,48}',
                re.IGNORECASE
            ),
            
            # JWT Tokens
            'jwt_token': re.compile(
                r'eyJ[A-Za-z0-9\-_]+\.eyJ[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+|'  # JWT format
                r'Bearer\s+eyJ[A-Za-z0-9\-_]+\.eyJ[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+',
                re.IGNORECASE
            ),
            
            # Private Keys
            'private_key': re.compile(
                r'-----BEGIN\s+(?:RSA|DSA|EC|OPENSSH|PGP)?\s*PRIVATE KEY(?:\s+BLOCK)?-----[\s\S]+?-----END\s+(?:RSA|DSA|EC|OPENSSH|PGP)?\s*PRIVATE KEY(?:\s+BLOCK)?-----',
                re.MULTILINE | re.IGNORECASE
            ),
            
            # SSH Keys
            'ssh_key': re.compile(
                r'ssh-(?:rsa|dss|ed25519)\s+[A-Za-z0-9+/]+[=]{0,2}(?:\s+[^\s]+)?'  # Public SSH key
            ),
            
            # Database Connection Strings
            'db_connection': re.compile(
                r'(?:mongodb(?:\+srv)?|postgres(?:ql)?|mysql|mssql|oracle|redis)://[^\s]+|'  # DB URLs
                r'(?:Server|Data Source)=[^;]+;(?:Initial Catalog|Database)=[^;]+;(?:User ID|UID)=[^;]+;(?:Password|PWD)=[^;]+',  # SQL Server
                re.IGNORECASE
            ),
            
            # OAuth Tokens
            'oauth_token': re.compile(
                r'(?:oauth[_\s]?token|access[_\s]?token|refresh[_\s]?token)[\s:=]*[A-Za-z0-9\-._~+/]{20,}',
                re.IGNORECASE
            ),
            
            # Stripe Keys
            'stripe_key': re.compile(
                r'(?:sk|pk)_(?:test|live)_[A-Za-z0-9]{24,}|'  # Stripe Secret/Public Keys
                r'(?:rk|whsec)_[A-Za-z0-9]{24,}',  # Restricted keys, Webhook secrets
                re.IGNORECASE
            ),
            
            # SendGrid Keys
            'sendgrid_key': re.compile(
                r'SG\.[A-Za-z0-9\-_]{22}\.[A-Za-z0-9\-_]{43}',
                re.IGNORECASE
            ),
            
            # Twilio Keys
            'twilio_key': re.compile(
                r'SK[a-z0-9]{32}|'  # Twilio API Key
                r'AC[a-z0-9]{32}',  # Twilio Account SID
                re.IGNORECASE
            ),
            
            # Mailgun Keys
            'mailgun_key': re.compile(
                r'key-[A-Za-z0-9]{32}',
                re.IGNORECASE
            ),
            
            # PayPal/Braintree
            'paypal_token': re.compile(
                r'access_token\$(?:production|sandbox)\$[A-Za-z0-9]{16}\$[A-Za-z0-9]{32}',
                re.IGNORECASE
            ),
            
            # Square Access Token
            'square_token': re.compile(
                r'sq0[a-z]{3}-[A-Za-z0-9\-_]{22}',
                re.IGNORECASE
            ),
            
            # Heroku API Key
            'heroku_key': re.compile(
                r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}',  # UUID format used by Heroku
                re.IGNORECASE
            ),
            
            # Generic Secret Patterns
            'generic_secret': re.compile(
                r'(?:secret|client[_\s]?secret|app[_\s]?secret)[\s:=]*[A-Za-z0-9\-_]{16,}|'
                r'(?:private[_\s]?key|priv[_\s]?key|secret[_\s]?key)[\s:=]*[A-Za-z0-9\-_]{16,}',
                re.IGNORECASE
            ),
            
            # Encryption Keys
            'encryption_key': re.compile(
                r'(?:encryption[_\s]?key|decrypt[_\s]?key|cipher[_\s]?key)[\s:=]*[A-Za-z0-9+/=]{16,}',
                re.IGNORECASE
            ),
            
            # Base64 encoded secrets (minimum 20 chars)
            'base64_secret': re.compile(
                r'(?:secret|key|token|password)[\s:=]*[A-Za-z0-9+/]{20,}={0,2}',
                re.IGNORECASE
            ),
            
            # Environment variable assignments with secrets
            'env_secret': re.compile(
                r'(?:export\s+)?(?:[A-Z_]{2,}(?:PASSWORD|SECRET|KEY|TOKEN|APIKEY|API_KEY))=["\']?[^\s"^\']+["\']?',
                re.MULTILINE
            )
        }
        return patterns
    
    def _normalize_text(self, text: str) -> str:
        return re.sub(r'\s+', ' ', text)
    
    def _calculate_name_score(self, text: str, context: str = "") -> float:
        """
        Calculate a confidence score for whether text is a name using multiple factors
        """
        score = 0.0
        text_lower = text.lower().strip()
        words = text_lower.split()
        
        # Check false positives first
        if text_lower in self.false_positive_names:
            return 0.0
        
        if any(word in self.false_positive_names for word in words):
            return 0.0
            
        # Basic validation
        if re.search(r'\d', text):  # Contains numbers
            score -= 0.5
        if len(text.replace(' ', '')) < 2:  # Too short
            return 0.0
        if re.match(r'^[^\w]+$', text):  # All punctuation
            return 0.0
            
        # Check known names databases
        for word in words:
            if word in self.common_first_names:
                score += 0.4
            if word in self.common_surnames:
                score += 0.3
            if word in self.sa_names:
                score += 0.35
                
        # Capitalization patterns
        if text[0].isupper():
            score += 0.1
        if all(w[0].isupper() for w in text.split() if w):
            score += 0.15
            
        # Name length and structure
        if 2 <= len(words) <= 4:
            score += 0.2
        if all(2 <= len(w) <= 15 for w in words):
            score += 0.1
            
        # Context analysis
        if context:
            context_lower = context.lower()
            # Check for name indicators before the potential name
            for indicator in self.name_context_words['before']:
                if indicator in context_lower[:50]:  # Check preceding context
                    score += 0.2
                    break
            # Check for name indicators after
            for indicator in self.name_context_words['after']:
                if indicator in context_lower[-50:]:  # Check following context
                    score += 0.15
                    break
                    
        # South African surname patterns
        sa_surname_patterns = ['van der', 'van', 'de', 'du', 'le', 'la']
        for pattern in sa_surname_patterns:
            if pattern in text_lower:
                score += 0.25
                
        # Name suffixes
        name_suffixes = ['son', 'sen', 'ing', 'er', 'man', 'ton', 'ley', 'field', 'wood', 'stone']
        if any(words[-1].endswith(suffix) for suffix in name_suffixes if words):
            score += 0.1
            
        return score
    
    def _is_likely_name(self, text: str, context: str = "") -> bool:
        """
        Enhanced name validation using confidence scoring
        """
        # Use scoring system with threshold
        score = self._calculate_name_score(text, context)
        
        # Threshold for name detection (adjustable based on requirements)
        threshold = 0.5
        
        # Additional validation for edge cases
        text_lower = text.lower().strip()
        words = text_lower.split()
        
        # Require at least 2 words for full names (unless very high confidence)
        if len(words) < 2 and score < 0.7:
            return False
            
        return score >= threshold
    
    def _extract_context(self, text: str, start: int, end: int, window: int = 50) -> str:
        """
        Extract context around a potential name for better validation
        """
        context_start = max(0, start - window)
        context_end = min(len(text), end + window)
        return text[context_start:context_end]
    
    def _get_named_entities(self, text: str) -> List[Tuple[str, int, int]]:
        """
        Get named entities using spaCy NER
        """
        entities = []
        try:
            doc = self.nlp(text)
            for ent in doc.ents:
                if ent.label_ == 'PERSON':
                    context = self._extract_context(text, ent.start_char, ent.end_char)
                    if self._is_likely_name(ent.text, context):
                        entities.append((ent.text, ent.start_char, ent.end_char))
                        logger.debug(f"NER detected person name: '{ent.text}' with score: {self._calculate_name_score(ent.text, context):.2f}")
                        
        except Exception as e:
            logger.warning(f"Error extracting named entities: {e}")
        
        return entities
    
    def _find_security_secrets(self, text: str) -> List[Tuple[int, int, str]]:
        """
        Find passwords, API keys, and other security secrets
        """
        matches = []
        
        # Additional context-based secret patterns
        secret_patterns = [
            # Password in context
            re.compile(r'(?:user|username)[\s:=]*[^\s,;]+[\s,;]+(?:password|pwd)[\s:=]*[^\s,;]+', re.IGNORECASE),
            # API credentials
            re.compile(r'(?:client[_\s]?id)[\s:=]*[^\s,;]+[\s,;]+(?:client[_\s]?secret)[\s:=]*[^\s,;]+', re.IGNORECASE),
            # Bearer tokens in headers
            re.compile(r'(?:Authorization|auth)[\s:]*Bearer\s+[A-Za-z0-9\-._~+/]+', re.IGNORECASE),
            # Basic auth
            re.compile(r'(?:Authorization|auth)[\s:]*Basic\s+[A-Za-z0-9+/]+=*', re.IGNORECASE),
            # API Headers
            re.compile(r'(?:X-API-Key|X-Auth-Token|X-Access-Token)[\s:]*[A-Za-z0-9\-._~+/]+', re.IGNORECASE),
        ]
        
        for pattern in secret_patterns:
            for match in pattern.finditer(text):
                matches.append((match.start(), match.end(), 'security_secret'))
                logger.debug(f"Security secret found: '{match.group()[:20]}...' (truncated for security)")
                
        return matches
    
    def _find_banking_details(self, text: str) -> List[Tuple[int, int, str]]:
        """
        Find South African banking and transaction details
        """
        matches = []
        
        # Look for banking keywords followed by numbers
        banking_patterns = [
            # Account details with context
            re.compile(r'\b(?:account|acc|acct)[\s:#]*(?:no|number|num)?[\s:#]*[\d\s-]{6,16}\b', re.IGNORECASE),
            # Reference numbers
            re.compile(r'\b(?:reference|ref)[\s:#]*[A-Z0-9\s-]{6,20}\b', re.IGNORECASE),
            # Transaction IDs
            re.compile(r'\b(?:transaction|trans|txn)[\s:#]*(?:id|no|number)?[\s:#]*[A-Z0-9]{6,20}\b', re.IGNORECASE),
            # Payment references
            re.compile(r'\b(?:payment|pay)[\s:#]*(?:ref|reference|id)?[\s:#]*[A-Z0-9]{6,20}\b', re.IGNORECASE),
            # Routing numbers
            re.compile(r'\b(?:routing|branch|sort)[\s:#]*(?:code|no|number)?[\s:#]*\d{6,9}\b', re.IGNORECASE),
            # Swift codes with context
            re.compile(r'\b(?:swift|bic)[\s:#]*[A-Z]{6,11}\b', re.IGNORECASE),
            # Card numbers with context
            re.compile(r'\b(?:card|credit|debit)[\s:#]*(?:no|number)?[\s:#]*[\d\s-]{13,19}\b', re.IGNORECASE),
        ]
        
        for pattern in banking_patterns:
            for match in pattern.finditer(text):
                matches.append((match.start(), match.end(), 'banking_detail'))
                logger.debug(f"Banking detail found: '{match.group().strip()}'")
                
        return matches
    
    def _find_names_with_patterns(self, text: str) -> List[Tuple[int, int, str]]:
        """
        Comprehensive regex-based name detection with multiple patterns
        """
        matches = []
        
        # Enhanced patterns for name detection
        name_patterns = [
            # Names with titles (including SA specific)
            re.compile(r'\b(?:Mr\.?|Mrs\.?|Ms\.?|Miss\.?|Dr\.?|Prof\.?|Professor\.?|Adv\.?|Advocate|Rev\.?|Reverend|Pastor|Fr\.?|Father|Sr\.?|Sister)\s+[A-Za-z\'\-]+(?:\s+[A-Za-z\'\-]+)*\b', re.IGNORECASE),
            
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
            
            # South African naming patterns (Afrikaans/Dutch origin)
            re.compile(r'\b[A-Za-z][a-z\'\-]*\s+(?:van\s+der\s+[A-Za-z][a-z\'\-]+|van\s+[A-Za-z][a-z\'\-]+|de\s+[A-Za-z][a-z\'\-]+|du\s+[A-Za-z][a-z\'\-]+|le\s+[A-Za-z][a-z\'\-]+|la\s+[A-Za-z][a-z\'\-]+)\b', re.IGNORECASE),
            
            # Indian/Muslim names common in SA
            re.compile(r'\b(?:Mohammed|Muhammad|Mohamed|Ahmad|Ahmed|Ali|Hassan|Hussein|Ibrahim|Ismail|Yusuf|Abdullah)\s+[A-Za-z][a-z\'\-]+\b', re.IGNORECASE),
            
            # Common SA name combinations
            re.compile(r'\b(?:Jan|Piet|Koos|Johan|Pieter|Hendrik|Willem|Andries|Francois|Jacques)\s+[A-Za-z][a-z\'\-]+\b', re.IGNORECASE),
            re.compile(r'\b(?:Thabo|Sipho|Mandla|Bongani|Sibusiso|Themba|Mpho|Tshepo)\s+[A-Za-z][a-z\'\-]+\b', re.IGNORECASE),
        ]
        
        for pattern in name_patterns:
            for match in pattern.finditer(text):
                match_text = match.group().strip()
                context = self._extract_context(text, match.start(), match.end())
                if self._is_likely_name(match_text, context):
                    matches.append((match.start(), match.end(), 'pattern_name'))
                    score = self._calculate_name_score(match_text, context)
                    logger.debug(f"Pattern detected name: '{match_text}' with score: {score:.2f}")
        
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
        
        # Get banking and transaction details
        banking_matches = self._find_banking_details(text)
        matches.extend(banking_matches)
        
        # Get security secrets (passwords, API keys, etc.)
        security_matches = self._find_security_secrets(text)
        matches.extend(security_matches)
        
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
            
            # Log summary of redactions by type
            redaction_summary = defaultdict(int)
            for _, _, match_type in matches:
                redaction_summary[match_type] += 1
            
            logger.info(f"Redacted {len(matches)} PII items: {dict(redaction_summary)}")
            
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
    
    Banking details:
    Account number: 4062511234567890
    Branch code: 250655
    Swift code: SBZAZAJJ
    Reference: TRN20241234567
    Amount: R 1,234.56
    Transaction ID: PAY789456123
    Card number: 4111 1111 1111 1111
    CVV: 123
    
    South African names:
    Thabo Mbeki and Pieter van der Merwe discussed with Mohammed Patel.
    Advocate Sipho Dlamini and Rev. Johannes Botha were present.
    Contact Precious Molefe or Blessing Nkosi for details.
    
    Security Credentials:
    password: MySecretPass123!
    api_key: sk_live_4242424242424242424242
    AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
    AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
    github_token: ghp_1234567890abcdefghijklmnopqrstuvwxyz
    database: mongodb://admin:password123@localhost:27017/mydb
    Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c
    client_secret: 6L3v3ryS3cr3tK3yF0rMyApp
    stripe_key: sk_test_4eC39HqLyjWDarjtT1zdp7dc
    AZURE_API_KEY=abc123def456ghi789jkl012mno345pqr678
    """
    
    redacted = redact_pii(test_text)
    print("Original text:")
    print(test_text)
    print("\nRedacted text:")
    print(redacted)
    
    # Test specific security patterns
    print("\n" + "="*50)
    print("Security Pattern Tests:")
    print("="*50)
    
    security_tests = [
        "My password is SuperSecret123!",
        "API_KEY=AIzaSyDrBGPeJVlahUANmBgd8n1Zh1I2tmA",
        "export DATABASE_URL=postgres://user:pass@localhost/db",
        "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQC user@host",
        "client_id: abc123 client_secret: xyz789secret",
        "-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA...\n-----END RSA PRIVATE KEY-----",
        "token: xoxb-123456789012-123456789012-abcdefghijklmnopqrstuv",
    ]
    
    for test in security_tests:
        redacted = redact_pii(test)
        print(f"\nOriginal: {test[:50]}..." if len(test) > 50 else f"\nOriginal: {test}")
        print(f"Redacted: {redacted[:50]}..." if len(redacted) > 50 else f"Redacted: {redacted}")