You are given my AI API codebase. 

You are an expert Python developer.

Your task is as follows: 

1. You must develop a PII redaction service in the apis/utils/ folder called redactPii.py. \
2. The function of the servuice will be to identify and redact the following pieces of PII and named entities in the provided text.
3. The input to this function will be a text input which the service must scan and redact pii
4. THe specified pii and named entities must be repleced with text [REDACTED] in the output
5. THe output will be passed to a LLM 

You must redact the following pieces of information:

1. Named entities
2. Customer Names and Surname
3. Postal Address or residential address
4. Soyth African phone numbers (starting with +27, +44, 011, 031, 021, 021, etc) or any other 10 digit phone number like 08212345678, 0112345678
5. South african Identity number (13-digit ID numbers)
6. Passport numbers
7. Banking details
8. Policy numbers (9 digit numeric numbers) 991123456, 555412315 

Please ensure that the redaction process is not case or white space sensitive - i.e if there is mixed case or spaces then this should not impact the output. 


Please use open source python packages and focus on accuracy! 

Follow the way that the other service functions in the api/utils folder have been implemented as the service need to used across multiple apis.