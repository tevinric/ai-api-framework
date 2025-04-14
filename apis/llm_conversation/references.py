# Predefined lists for vehicle data validation
CAR_MAKES = [
    "Toyota", "Honda", "Ford", "Volkswagen", "BMW", "Mercedes-Benz", "Audi", 
    "Nissan", "Hyundai", "Kia", "Mazda", "Subaru", "Lexus", "Chevrolet", 
    "Jeep", "Volvo", "Land Rover", "Porsche", "Ferrari", "Tesla"
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
    "Ferrari": ["488", "F8 Tributo", "812", "Roma", "SF90", "Portofino"],
    "Tesla": ["Model 3", "Model S", "Model X", "Model Y", "Cybertruck"]
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

# Cover types
COVER_TYPES = [
    "Comprehensive",
    "Advensure",
    "Third Party, Fire and Theft",
    "Auto&General Expresss 1",
    "Auto&General Express 2",
    "Auto&General Express 3"
]

# Insured value options
INSURED_VALUE_OPTIONS = [
    "Market Value",
    "Retail value",
    "Trade value",
    "BetterCar"
]

# Night parking locations
NIGHT_PARKING_LOCATIONS = [
    "Basement",
    "Carport",
    "Driveway/yard",
    "Garage",
    "Open Parking lot",
    "Pevement/street"
]

# Night parking security types
NIGHT_PARKING_SECURITY_TYPES = [
    "Security guarded access control",
    "Electronic access control",
    "Locked gate",
    "None"
]

# Define cost in credits for using the insurance bot
INSURANCE_BOT_CREDIT_COST = 1

# Define GPT-4o deployment model
GPT4O_DEPLOYMENT = "gpt-4o"

# Conversation state
CONVERSATION_STATE = "vehicle_quote"

# Off-topic response template
OFF_TOPIC_RESPONSE = (
    "I'm specialized in helping you get a vehicle insurance quote. Let's focus on getting your quote completed. "
    "Could you please tell me about the vehicle you'd like to insure?"
)

# System message for vehicle insurance quote bot
VEHICLE_QUOTE_SYSTEM_MESSAGE = """
You are VehicleQuoteBot, a specialized assistant focused solely on gathering information to provide vehicle insurance quotes. Your only job is to collect the necessary details in a conversational manner.

Important rules:
- Focus exclusively on vehicle insurance quotes - do not discuss any other insurance types or topics.
- If the user asks about anything unrelated to vehicle insurance quotes, politely redirect them back to the vehicle quote process.
- Use a friendly, professional tone while collecting information.
- Collect information step-by-step in a natural conversation flow.
- Do not calculate or provide actual premium amounts - just collect the information.
- When all required information is collected, provide a clear summary of all collected information.

Information you need to collect (in a conversational way):
1. Personal details:
   - Customer name
   - ID number

2. Vehicle details:
   - Vehicle make (e.g., Toyota, BMW, Ford)
   - Vehicle model (e.g., Corolla, 5 Series, Ranger)
   - Vehicle year (e.g., 2018, 2022)
   - Vehicle color (e.g., Red, White, Black)
   - Vehicle usage (one of the following):
     * Private and/or travelling to work
     * Private and occasional business
     * Private and full business
   - Is the vehicle registered in South Africa? (Yes/No)
   - Is the vehicle financed? (Yes/No)

3. Coverage preferences:
   - Cover type (one of the following):
     * Comprehensive
     * Advensure
     * Third Party, Fire and Theft
     * Auto&General Expresss 1
     * Auto&General Express 2
     * Auto&General Express 3
   - Insured value preference (one of the following):
     * Market Value
     * Retail value
     * Trade value
     * BetterCar

4. Risk details:
   - Area/suburb where the vehicle is normally parked at night
   - Night parking location (one of the following):
     * Basement
     * Carport
     * Driveway/yard
     * Garage
     * Open Parking lot
     * Pevement/street
   - Security features where the vehicle is parked (can select multiple):
     * Security guarded access control
     * Electronic access control
     * Locked gate
     * None

Use the collect_vehicle_info function when it makes sense to record information the user has provided.
Use the process_vehicle_quote function when all required information has been collected.

Always maintain focus on getting a vehicle insurance quote and redirect if the conversation veers off-topic.
"""

# Function definitions for GPT-4o
VEHICLE_QUOTE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "collect_vehicle_info",
            "description": "Record information about the vehicle and the customer for the insurance quote",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_name": {
                        "type": "string",
                        "description": "The customer's full name"
                    },
                    "id_number": {
                        "type": "string",
                        "description": "The customer's ID number"
                    },
                    "make": {
                        "type": "string",
                        "description": "Make of the vehicle (e.g., Toyota, BMW)"
                    },
                    "model": {
                        "type": "string",
                        "description": "Model of the vehicle (e.g., Corolla, X5)"
                    },
                    "year": {
                        "type": "string",
                        "description": "Year of the vehicle (e.g., 2020)"
                    },
                    "color": {
                        "type": "string",
                        "description": "Color of the vehicle"
                    },
                    "usage": {
                        "type": "string",
                        "description": "How the vehicle will be used",
                        "enum": [
                            "Private and/or travelling to work",
                            "Private and occasional business",
                            "Private and full business"
                        ]
                    },
                    "is_registered_in_sa": {
                        "type": "boolean",
                        "description": "Whether the vehicle is registered in South Africa"
                    },
                    "is_financed": {
                        "type": "boolean",
                        "description": "Whether the vehicle is financed"
                    },
                    "cover_type": {
                        "type": "string",
                        "description": "Type of insurance coverage",
                        "enum": [
                            "Comprehensive",
                            "Advensure",
                            "Third Party, Fire and Theft",
                            "Auto&General Expresss 1",
                            "Auto&General Express 2",
                            "Auto&General Express 3"
                        ]
                    },
                    "insured_value": {
                        "type": "string",
                        "description": "Preferred insured value option",
                        "enum": [
                            "Market Value",
                            "Retail value",
                            "Trade value",
                            "BetterCar"
                        ]
                    },
                    "night_parking_area": {
                        "type": "string",
                        "description": "Area or suburb where the car is normally parked at night"
                    },
                    "night_parking_location": {
                        "type": "string",
                        "description": "Location type where the car is normally parked at night",
                        "enum": [
                            "Basement",
                            "Carport",
                            "Driveway/yard",
                            "Garage",
                            "Open Parking lot",
                            "Pevement/street"
                        ]
                    },
                    "night_parking_security": {
                        "type": "array",
                        "description": "Security features where the car is parked at night",
                        "items": {
                            "type": "string",
                            "enum": [
                                "Security guarded access control",
                                "Electronic access control",
                                "Locked gate",
                                "None"
                            ]
                        }
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "process_vehicle_quote",
            "description": "Process a vehicle insurance quote when all required information has been collected",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_name": {
                        "type": "string",
                        "description": "The customer's full name"
                    },
                    "id_number": {
                        "type": "string",
                        "description": "The customer's ID number"
                    },
                    "vehicle_details": {
                        "type": "object",
                        "description": "Details about the vehicle to insure",
                        "properties": {
                            "make": {
                                "type": "string",
                                "description": "Make of the vehicle (e.g., Toyota, BMW)"
                            },
                            "model": {
                                "type": "string",
                                "description": "Model of the vehicle (e.g., Corolla, X5)"
                            },
                            "year": {
                                "type": "string",
                                "description": "Year of the vehicle (e.g., 2020)"
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
                            }
                        },
                        "required": ["make", "model", "year", "color", "usage", "is_registered_in_sa", "is_financed"]
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
                        "description": "Details about the risk factors",
                        "properties": {
                            "night_parking_area": {
                                "type": "string",
                                "description": "Area or suburb where the car is normally parked at night"
                            },
                            "night_parking_location": {
                                "type": "string",
                                "description": "Location type where the car is normally parked at night"
                            },
                            "night_parking_security": {
                                "type": "array",
                                "description": "Security features where the car is parked at night",
                                "items": {
                                    "type": "string"
                                }
                            }
                        },
                        "required": ["night_parking_area", "night_parking_location", "night_parking_security"]
                    }
                },
                "required": ["customer_name", "id_number", "vehicle_details", "coverage_details", "risk_details"]
            }
        }
    }
]

# Define container for insurance conversation histories
INSURANCE_CONVERSATION_CONTAINER = "insurance-bot-conversations"
