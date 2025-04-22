"""
Validation utilities for car insurance quote data
"""
import re
from datetime import datetime
from apis.car_insurance.references import (
    CAR_MAKES, CAR_MODELS_BY_MAKE, MODEL_TYPES_BY_MODEL, CAR_COLORS,
    VEHICLE_USAGE_TYPES, COVER_TYPES, INSURED_VALUE_OPTIONS,
    PARKING_LOCATIONS, PARKING_SECURITY_TYPES,
    MARITAL_STATUS_OPTIONS, EMPLOYMENT_STATUS_OPTIONS
)

def validate_sa_id(id_number):
    """
    Validate South African ID number
    
    Args:
        id_number (str): ID number to validate
        
    Returns:
        tuple: (bool, str) - (is_valid, error_message)
    """
    # Remove spaces and hyphens
    id_number = re.sub(r'[\s-]', '', id_number)
    
    # Check if it's a 13-digit number
    if not re.match(r'^\d{13}$', id_number):
        return False, "South African ID number must be 13 digits"
    
    # Extract birth date (first 6 digits: YYMMDD)
    try:
        year_prefix = '19' if int(id_number[0:2]) > 50 else '20'
        birth_date_str = year_prefix + id_number[0:6]
        birth_date = datetime.strptime(birth_date_str, '%Y%m%d')
        
        # Basic birth date validation
        current_date = datetime.now()
        age = current_date.year - birth_date.year - (
            (current_date.month, current_date.day) < (birth_date.month, birth_date.day))
        
        if age < 16:
            return False, "Driver must be at least 16 years old"
        if age > 100:
            return False, "Birth date indicates an age over 100 years"
    except ValueError:
        return False, "Invalid birth date in ID number"
    
    # Extract gender (7th digit: 0-4 for female, 5-9 for male)
    gender_digit = int(id_number[6])
    parsed_gender = "Male" if gender_digit >= 5 else "Female"
    
    # Extract citizenship (11th digit: 0 for SA citizen, 1 for permanent resident)
    citizenship_digit = int(id_number[10])
    citizenship = "South African Citizen" if citizenship_digit == 0 else "Permanent Resident"
    
    # Validate check digit (Luhn algorithm - simplified)
    try:
        # 1. Add all digits in odd positions (1, 3, 5, etc.)
        odd_sum = sum(int(id_number[i]) for i in range(0, 12, 2))
        
        # 2. Concatenate even position digits (2, 4, 6, etc.)
        even_digits = ''.join(id_number[i] for i in range(1, 12, 2))
        
        # 3. Multiply by 2
        even_doubled = str(int(even_digits) * 2)
        
        # 4. Add all single digits in the result
        even_sum = sum(int(digit) for digit in even_doubled)
        
        # 5. Add odd and even sums
        total_sum = odd_sum + even_sum
        
        # 6. The control digit is the number that must be added to make total_sum
        # a multiple of 10
        control_digit = (10 - (total_sum % 10)) % 10
        
        # 7. Check if control digit matches the last digit of ID number
        if control_digit != int(id_number[12]):
            return False, "ID number has an invalid check digit"
    except Exception:
        return False, "Unable to verify ID number checksum"
    
    # Return success with extracted info
    return True, {
        "birth_date": birth_date.strftime("%Y-%m-%d"),
        "gender": parsed_gender,
        "citizenship": citizenship
    }

def validate_email(email):
    """
    Validate email address format
    
    Args:
        email (str): Email address to validate
        
    Returns:
        tuple: (bool, str) - (is_valid, error_message)
    """
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    
    if not re.match(email_pattern, email):
        return False, "Invalid email address format"
    
    # Check for common mistakes
    if '..' in email or email.startswith('.') or email.endswith('.'):
        return False, "Email contains consecutive dots or starts/ends with a dot"
    
    # Check domain
    domain = email.split('@')[1]
    if len(domain) > 255:
        return False, "Email domain is too long"
    
    return True, "Email is valid"

def validate_sa_phone(phone):
    """
    Validate South African phone number
    
    Args:
        phone (str): Phone number to validate
        
    Returns:
        tuple: (bool, str) - (is_valid, error_message)
    """
    # Remove spaces, hyphens, brackets
    phone = re.sub(r'[\s\-\(\)]', '', phone)
    
    # Convert international format to local
    if phone.startswith('+27'):
        phone = '0' + phone[3:]
    
    # Check format
    if not re.match(r'^0\d{9}$', phone):
        return False, "South African phone number must be 10 digits starting with 0"
    
    # Check for valid mobile prefixes
    mobile_prefixes = ['060', '061', '062', '063', '064', '065', '066', '067', '068', '071', '072', '073', '074', '076', '078', '079', '081', '082', '083', '084']
    if not any(phone.startswith(prefix) for prefix in mobile_prefixes):
        return False, "Phone number doesn't start with a valid South African mobile prefix"
    
    return True, "Phone number is valid"

def validate_vehicle_year(year):
    """
    Validate vehicle year is reasonable
    
    Args:
        year (str or int): Vehicle year to validate
        
    Returns:
        tuple: (bool, str) - (is_valid, error_message)
    """
    try:
        year = int(year)
        current_year = datetime.now().year
        
        if year < 1950:
            return False, f"Year {year} seems too old. Please provide a year between 1950 and {current_year + 1}"
        
        if year > current_year + 1:
            return False, f"Year {year} is in the future. Please provide a year between 1950 and {current_year + 1}"
        
        return True, "Vehicle year is valid"
    except ValueError:
        return False, f"'{year}' is not a valid year. Please provide a numeric year (e.g., 2020)"

def validate_name(name):
    """
    Validate customer name
    
    Args:
        name (str): Customer name to validate
        
    Returns:
        tuple: (bool, str) - (is_valid, error_message)
    """
    # Trim whitespace
    name = name.strip()
    
    # Check if empty
    if not name:
        return False, "Name cannot be empty"
    
    # Check if it contains at least a first and last name
    parts = name.split()
    if len(parts) < 2:
        return False, "Please provide both your first and last name"
    
    # Check length
    if len(name) < 3:
        return False, "Name is too short"
    
    if len(name) > 100:
        return False, "Name is too long"
    
    # Check for test or profanity indicators (simplified check)
    test_terms = ["test", "tester", "testing", "abc", "xyz", "123", "fuck", "shit", "dummy"]
    for part in parts:
        if part.lower() in test_terms:
            return False, "Please provide your actual name"
    
    # Check for valid characters
    if not re.match(r'^[A-Za-z\s\.\-\']+$', name):
        return False, "Name contains invalid characters. Only letters, spaces, hyphens, periods, and apostrophes are allowed"
    
    return True, "Name is valid"

def extract_gender_from_id(id_number):
    """
    Extract gender from South African ID number
    
    Args:
        id_number (str): SA ID number
        
    Returns:
        str or None: 'Male', 'Female', or None if invalid
    """
    # Remove spaces and hyphens
    id_number = re.sub(r'[\s-]', '', id_number)
    
    # Check if it's a 13-digit number
    if not re.match(r'^\d{13}$', id_number):
        return None
    
    # Extract gender (7th digit: 0-4 for female, 5-9 for male)
    try:
        gender_digit = int(id_number[6])
        return "Male" if gender_digit >= 5 else "Female"
    except (IndexError, ValueError):
        return None

def get_validation_results(extraction_data):
    """
    Run validation on all extraction data fields and return results
    
    Args:
        extraction_data (dict): The collected data to validate
        
    Returns:
        dict: Validation results with errors for each field
    """
    results = {
        "valid": True,
        "field_errors": {}
    }
    
    # ID number
    if "id_number" in extraction_data and extraction_data["id_number"]:
        is_valid, message = validate_sa_id(extraction_data["id_number"])
        if not is_valid:
            results["valid"] = False
            results["field_errors"]["id_number"] = message
            
    # Email
    if "email_address" in extraction_data and extraction_data["email_address"]:
        is_valid, message = validate_email(extraction_data["email_address"])
        if not is_valid:
            results["valid"] = False
            results["field_errors"]["email_address"] = message
            
    # Phone
    if "cellphone_number" in extraction_data and extraction_data["cellphone_number"]:
        is_valid, message = validate_sa_phone(extraction_data["cellphone_number"])
        if not is_valid:
            results["valid"] = False
            results["field_errors"]["cellphone_number"] = message
            
    # Vehicle year
    if "year" in extraction_data and extraction_data["year"]:
        is_valid, message = validate_vehicle_year(extraction_data["year"])
        if not is_valid:
            results["valid"] = False
            results["field_errors"]["year"] = message
            
    # Name
    if "customer_name" in extraction_data and extraction_data["customer_name"]:
        is_valid, message = validate_name(extraction_data["customer_name"])
        if not is_valid:
            results["valid"] = False
            results["field_errors"]["customer_name"] = message
            
    # Gender-ID matching validation
    if "gender" in extraction_data and extraction_data["gender"] and "id_number" in extraction_data and extraction_data["id_number"]:
        extracted_gender = extract_gender_from_id(extraction_data["id_number"])
        if extracted_gender and extracted_gender != extraction_data["gender"]:
            results["valid"] = False
            results["field_errors"]["gender"] = f"Gender does not match the gender encoded in your ID number ({extracted_gender})"
    
    return results
