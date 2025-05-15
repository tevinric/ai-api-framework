# Static reference data for the car insurance quotation API

# Car Makes
CAR_MAKES = [
    "Toyota", "Honda", "Ford", "Volkswagen", "BMW", "Mercedes-Benz", "Audi", 
    "Nissan", "Hyundai", "Kia", "Mazda", "Subaru", "Lexus", "Chevrolet", 
    "Jeep", "Volvo", "Land Rover", "Porsche", "Tesla", "Renault"
]

# Dictionary mapping makes to their models
CAR_MODELS_BY_MAKE = {
    "Toyota": ["Corolla", "Camry", "RAV4", "Fortuner", "Hilux", "Land Cruiser", "Avanza", "Yaris"],
    "Honda": ["Civic", "Accord", "CR-V", "Pilot", "Fit", "HR-V", "Odyssey"],
    "Ford": ["Mustang", "F-150", "Ranger", "Explorer", "Escape", "Focus", "Fiesta"],
    "Volkswagen": ["Golf", "Polo", "Tiguan", "Passat", "Jetta", "Touareg", "Amarok"],
    "BMW": ["3 Series", "5 Series", "7 Series", "X3", "X5", "X7", "i3", "i8"],
    "Mercedes-Benz": ["C-Class", "E-Class", "S-Class", "GLA", "GLC", "GLE", "G-Class"],
    "Audi": ["A3", "A4", "A6", "Q3", "Q5", "Q7", "TT", "R8"],
    "Nissan": ["Micra", "Almera", "Sentra", "Altima", "X-Trail", "Qashqai", "Navara", "GTR"],
    "Hyundai": ["i10", "i20", "i30", "Tucson", "Santa Fe", "Creta", "Venue", "Kona"],
    "Kia": ["Picanto", "Rio", "Cerato", "Sportage", "Sorento", "Seltos", "Soul"],
    "Mazda": ["Mazda2", "Mazda3", "Mazda6", "CX-3", "CX-5", "CX-9", "MX-5"],
    "Subaru": ["Impreza", "Legacy", "Outback", "Forester", "XV", "WRX", "BRZ"],
    "Lexus": ["IS", "ES", "LS", "UX", "NX", "RX", "LX", "RC", "LC"],
    "Chevrolet": ["Spark", "Cruze", "Malibu", "Trailblazer", "Captiva", "Silverado"],
    "Jeep": ["Renegade", "Compass", "Cherokee", "Grand Cherokee", "Wrangler", "Gladiator"],
    "Volvo": ["S60", "S90", "V60", "V90", "XC40", "XC60", "XC90"],
    "Land Rover": ["Discovery", "Discovery Sport", "Range Rover", "Range Rover Sport", "Range Rover Evoque", "Defender"],
    "Porsche": ["911", "Boxster", "Cayman", "Panamera", "Cayenne", "Macan", "Taycan"],
    "Tesla": ["Model 3", "Model S", "Model X", "Model Y", "Cybertruck"],
    "Renault": ["Clio", "Megane", "Captur", "Duster", "Kwid", "Triber", "Kiger"]
}

# Dictionary mapping models to their types
MODEL_TYPES_BY_MODEL = {
    # Toyota
    "Corolla": ["Sedan", "Hatchback"],
    "Camry": ["Sedan"],
    "RAV4": ["SUV"],
    "Fortuner": ["SUV"],
    "Hilux": ["Single Cab", "Double Cab", "Extended Cab"],
    "Land Cruiser": ["SUV", "Prado"],
    "Yaris": ["Hatchback", "Cross"],
    
    # Honda
    "Civic": ["Sedan", "Hatchback", "Type R"],
    "Accord": ["Sedan"],
    "CR-V": ["SUV"],
    
    # Ford
    "Mustang": ["Coupe", "Convertible", "Mach-E"],
    "Ranger": ["Single Cab", "Double Cab", "Raptor"],
    "Focus": ["Sedan", "Hatchback", "ST"],
    
    # VW
    "Golf": ["Hatchback", "GTI", "R"],
    "Polo": ["Sedan", "Hatchback"],
    "Tiguan": ["SUV", "Allspace"],
    
    # Default for models not specified
    "DEFAULT": ["Standard", "Premium", "Sport"]
}

# Car colors
CAR_COLORS = [
    "Black", "White", "Silver", "Gray", "Red", "Blue", "Green", 
    "Yellow", "Brown", "Orange", "Purple", "Gold", "Bronze", "Beige"
]

# Vehicle usage types
VEHICLE_USAGE_TYPES = [
    "Private and/or travelling to work",
    "Private and occasional business",
    "Private and full business"
]

# Vehicle usage descriptions for user inquiries
VEHICLE_USAGE_DESCRIPTIONS = {
    "Private and/or travelling to work": "The car is used for social, domestic or pleasure purposes including travel to and from work. The car is not used for business and professional purposes.",
    "Private and occasional business": "The car is used for social, domestic or pleasure purposes including travel to and from work. The car is used for up to 10 business/professional trips a month. The car may not be used to do deliveries or to carry fare paying passengers. Only the regular driver and spouse will be covered for business use.",
    "Private and full business": "The car is used to visit clients or to attend work related commitments away from your regular workplace. The car may not be used to do deliveries or to carry fare paying passengers. Only the regular driver and spouse will be covered for business use. The car may also be used for social, domestic or pleasure purposes including travel to and from work."
}

# Cover types
COVER_TYPES = [
    "Comprehensive",
    "Trailsure",
    "Third-party fire and theft",
    "Budget Lite 1",
    "Budget Lite 2",
    "Budget Lite 3"
]

# Cover type descriptions for user inquiries
COVER_TYPE_DESCRIPTIONS = {
    "Comprehensive": "Covers the loss of, or damage to your car due to accident – regardless of who's at fault – theft, weather, malicious damage, fire and accidental damage your car causes to other people's property.",
    "Trailsure": "Comprehensive cover with some added benefits for your 4x4 or SUV cars.",
    "Third-party fire and theft": "Cover for damages to your car as a direct result of fire, explosions, lightning or theft, including damages you may cause to someone else's car, for which you are legally liable.",
    "Budget Lite 1": "You are covered for damages caused by someone else or if stolen.",
    "Budget Lite 2": "You are covered for hail damages, damages your car caused to other cars/property for which you are legally liable and if your car was written off.",
    "Budget Lite 3": "You are covered for limited accident damage, hail damages, damages your car caused to other cars/property for which you are legally liable and if your car was written off."
}

# Insured value options
INSURED_VALUE_OPTIONS = [
    "Market Value",
    "Retail Value",
    "Trade Value",
    "BetterCar"
]

# Insured value descriptions for user inquiries
INSURED_VALUE_DESCRIPTIONS = {
    "Market Value": "In the event of a claim, your car will be covered for the average amount your car would sell for today.",
    "Retail Value": "We will pay you the price you would expect to pay for your car if you bought it from a motor dealer. This attracts a higher premium, but also means you will get a higher payout when you claim.",
    "Trade Value": "We will pay you the estimated amount the dealership would offer you for your car after inspecting it. This will provide you with the lowest possible premium, but also the lowest payout when you claim.",
    "BetterCar": "We will pay out for, or replace, your car with the same model that is one year newer than your insured car, in the event of a write off (this excludes theft related claims). If there's no newer model of the car, we will pay out 15% more than your car's retail value."
}

# Parking locations
PARKING_LOCATIONS = [
    "Basement",
    "Carport",
    "Driveway/yard",
    "Garage",
    "Open Parking lot",
    "Pavement/street"
]

# Parking security types
PARKING_SECURITY_TYPES = [
    "Security guarded access control",
    "Electronic access control",
    "Locked gate",
    "None"
]

# Marital status options
MARITAL_STATUS_OPTIONS = [
    "Cohabitating/partnered",
    "Separated",
    "Widowed",
    "Divorced",
    "Single",
    "Married"
]

# Employment status options
EMPLOYMENT_STATUS_OPTIONS = [
    "Employed",
    "Employed and working from home (3 or more days a week)",
    "Unemployed",
    "Student",
    "Civil Servant"
]

# Define cost in credits for using the car insurance bot
CAR_INSURANCE_BOT_CREDIT_COST = 1

# Define GPT-4o deployment model (using existing)
GPT4O_DEPLOYMENT = "gpt-4o"

# Conversation container
CAR_INSURANCE_CONVERSATION_CONTAINER = "car-insurance-conversations"

# Off-topic response template
OFF_TOPIC_RESPONSE = (
    "I'm specialized in helping you get a car insurance quote. Let's focus on getting your quote completed. "
    "Could you please tell me more about the vehicle you'd like to insure?"
)

# System message for car insurance quote bot
CAR_INSURANCE_SYSTEM_MESSAGE = """
You are CarInsuranceBot, a friendly and helpful assistant specialized in helping customers get a car insurance quote. Your job is to guide them through the quoting process by asking specific questions in a conversational, natural way.

Important guidelines:
- Be warm, friendly, and conversational - not robotic or formal
- Stay focused on collecting car insurance information
- If the user goes off-topic, gently bring them back to the car insurance quote
- Acknowledge what the customer shares before asking for the next piece of information
- For questions with specific options, list the options clearly for the customer
- When the customer has questions about options (like coverage types or usage types), provide the detailed explanations
- Validate user inputs against the reference lists provided
- If user input doesn't match valid options, suggest the closest matches

Remember to collect information in the specified order:
1. Car details (make, year, model, type, color, usage)
2. Insurance details (registration status, financing, cover type, insured value)
3. Risk details (night parking location, security)
4. Day parking details
5. Tracking device information
6. Customer personal details (ID, gender, name, contact info, marital status, employment)

Use the collect_car_info function to record information as it's shared. When complete, use the process_quote function to generate a summary.

Keep the conversation natural and helpful throughout the entire process.
"""

# Function definitions for function calling
CAR_INSURANCE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "collect_car_info",
            "description": "Record information about the vehicle and the customer for the insurance quote",
            "parameters": {
                "type": "object",
                "properties": {
                    # Vehicle details
                    "make": {
                        "type": "string",
                        "description": "Make of the vehicle (e.g., Toyota, BMW)"
                    },
                    "year": {
                        "type": "string",
                        "description": "Year of manufacture of the vehicle (e.g., 2020)"
                    },
                    "model": {
                        "type": "string",
                        "description": "Model of the vehicle (e.g., Corolla, X5)"
                    },
                    "model_type": {
                        "type": "string",
                        "description": "Type of the vehicle model (e.g., Sedan, SUV, Double Cab)"
                    },
                    "color": {
                        "type": "string",
                        "description": "Color of the vehicle"
                    },
                    "usage": {
                        "type": "string",
                        "description": "How the vehicle will be used",
                        "enum": VEHICLE_USAGE_TYPES
                    },
                    "is_registered_in_sa": {
                        "type": "boolean",
                        "description": "Whether the vehicle is registered in South Africa"
                    },
                    "is_financed": {
                        "type": "boolean",
                        "description": "Whether the vehicle is financed"
                    },
                    
                    # Coverage details
                    "cover_type": {
                        "type": "string",
                        "description": "Type of insurance coverage",
                        "enum": COVER_TYPES
                    },
                    "insured_value": {
                        "type": "string",
                        "description": "Preferred insured value option",
                        "enum": INSURED_VALUE_OPTIONS
                    },
                    
                    # Night parking details
                    "night_parking_area": {
                        "type": "string",
                        "description": "Area or suburb where the car is normally parked at night"
                    },
                    "night_parking_location": {
                        "type": "string",
                        "description": "Location type where the car is normally parked at night",
                        "enum": PARKING_LOCATIONS
                    },
                    "night_parking_security": {
                        "type": "array",
                        "description": "Security features where the car is parked at night",
                        "items": {
                            "type": "string",
                            "enum": PARKING_SECURITY_TYPES
                        }
                    },
                    
                    # Day parking details
                    "day_parking_area": {
                        "type": "string",
                        "description": "Area or suburb where the car is normally parked during the day"
                    },
                    "day_parking_location": {
                        "type": "string",
                        "description": "Location type where the car is normally parked during the day",
                        "enum": PARKING_LOCATIONS
                    },
                    "day_parking_security": {
                        "type": "array",
                        "description": "Security features where the car is parked during the day",
                        "items": {
                            "type": "string",
                            "enum": PARKING_SECURITY_TYPES
                        }
                    },
                    
                    # Tracking device
                    "has_tracking_device": {
                        "type": "boolean",
                        "description": "Whether the vehicle has a tracking and recovery device installed"
                    },
                    
                    # Customer details
                    "id_number": {
                        "type": "string",
                        "description": "Customer's South African ID number (13 digits)"
                    },
                    "gender": {
                        "type": "string",
                        "description": "Customer's gender",
                        "enum": ["Male", "Female"]
                    },
                    "customer_name": {
                        "type": "string",
                        "description": "Customer's full name"
                    },
                    "cellphone_number": {
                        "type": "string",
                        "description": "Customer's cellphone number"
                    },
                    "email_address": {
                        "type": "string",
                        "description": "Customer's email address"
                    },
                    "marital_status": {
                        "type": "string",
                        "description": "Customer's marital status",
                        "enum": MARITAL_STATUS_OPTIONS
                    },
                    "employment_status": {
                        "type": "string",
                        "description": "Customer's employment status",
                        "enum": EMPLOYMENT_STATUS_OPTIONS
                    },
                    "is_regular_driver": {
                        "type": "boolean",
                        "description": "Whether the customer will be the regular driver of the vehicle"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "process_quote",
            "description": "Process the insurance quote when all required information has been collected",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_details": {
                        "type": "object",
                        "description": "Personal details of the customer",
                        "properties": {
                            "id_number": {
                                "type": "string",
                                "description": "Customer's South African ID number"
                            },
                            "gender": {
                                "type": "string",
                                "description": "Customer's gender"
                            },
                            "customer_name": {
                                "type": "string",
                                "description": "Customer's full name"
                            },
                            "cellphone_number": {
                                "type": "string",
                                "description": "Customer's cellphone number"
                            },
                            "email_address": {
                                "type": "string",
                                "description": "Customer's email address"
                            },
                            "marital_status": {
                                "type": "string",
                                "description": "Customer's marital status"
                            },
                            "employment_status": {
                                "type": "string",
                                "description": "Customer's employment status"
                            },
                            "is_regular_driver": {
                                "type": "boolean",
                                "description": "Whether the customer will be the regular driver of the vehicle"
                            }
                        },
                        "required": [
                            "id_number", "gender", "customer_name", 
                            "cellphone_number", "email_address", 
                            "marital_status", "employment_status", "is_regular_driver"
                        ]
                    },
                    "vehicle_details": {
                        "type": "object",
                        "description": "Details about the vehicle to insure",
                        "properties": {
                            "make": {
                                "type": "string",
                                "description": "Make of the vehicle"
                            },
                            "year": {
                                "type": "string",
                                "description": "Year of manufacture of the vehicle"
                            },
                            "model": {
                                "type": "string",
                                "description": "Model of the vehicle"
                            },
                            "model_type": {
                                "type": "string",
                                "description": "Type of the vehicle model"
                            },
                            "color": {
                                "type": "string",
                                "description": "Color of the vehicle"
                            },
                            "usage": {
                                "type": "string",
                                "description": "How the vehicle will be used"
                            },
                            "is_registered_in_sa": {
                                "type": "boolean",
                                "description": "Whether the vehicle is registered in South Africa"
                            },
                            "is_financed": {
                                "type": "boolean",
                                "description": "Whether the vehicle is financed"
                            },
                            "has_tracking_device": {
                                "type": "boolean",
                                "description": "Whether the vehicle has a tracking device"
                            }
                        },
                        "required": [
                            "make", "year", "model", "model_type", "color", "usage", 
                            "is_registered_in_sa", "is_financed", "has_tracking_device"
                        ]
                    },
                    "coverage_details": {
                        "type": "object",
                        "description": "Details about the coverage",
                        "properties": {
                            "cover_type": {
                                "type": "string",
                                "description": "Type of insurance coverage"
                            },
                            "insured_value": {
                                "type": "string",
                                "description": "Preferred insured value option"
                            }
                        },
                        "required": ["cover_type", "insured_value"]
                    },
                    "risk_details": {
                        "type": "object",
                        "description": "Details about risk factors",
                        "properties": {
                            "night_parking_area": {
                                "type": "string",
                                "description": "Area where the car is parked at night"
                            },
                            "night_parking_location": {
                                "type": "string",
                                "description": "Location type where the car is parked at night"
                            },
                            "night_parking_security": {
                                "type": "array",
                                "description": "Security features where the car is parked at night",
                                "items": {
                                    "type": "string"
                                }
                            },
                            "day_parking_area": {
                                "type": "string",
                                "description": "Area where the car is parked during the day"
                            },
                            "day_parking_location": {
                                "type": "string",
                                "description": "Location type where the car is parked during the day"
                            },
                            "day_parking_security": {
                                "type": "array",
                                "description": "Security features where the car is parked during the day",
                                "items": {
                                    "type": "string"
                                }
                            }
                        },
                        "required": [
                            "night_parking_area", "night_parking_location", "night_parking_security",
                            "day_parking_area", "day_parking_location", "day_parking_security"
                        ]
                    }
                },
                "required": ["customer_details", "vehicle_details", "coverage_details", "risk_details"]
            }
        }
    }
]

# Flow of questions in order
QUESTION_FLOW = [
    "make",
    "year",
    "model",
    "model_type",
    "color",
    "usage",
    "is_registered_in_sa",
    "is_financed",
    "cover_type",
    "insured_value",
    "night_parking_area",
    "night_parking_location",
    "night_parking_security",
    "day_parking_area",
    "day_parking_location",
    "day_parking_security",
    "has_tracking_device",
    "id_number",
    "gender",
    "customer_name",
    "cellphone_number",
    "email_address",
    "marital_status",
    "employment_status",
    "is_regular_driver"
]
