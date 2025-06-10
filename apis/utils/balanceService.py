from datetime import datetime, date
import logging
import pytz
from apis.utils.databaseService import DatabaseService

logger = logging.getLogger(__name__)

class BalanceService:
    @staticmethod
    def get_first_day_of_month():
        """Get first day of current month in SAST timezone"""
        sast = pytz.timezone('Africa/Johannesburg')
        current_date = datetime.now(sast)
        return date(current_date.year, current_date.month, 1)

    @staticmethod
    def initialize_monthly_balance(user_id):
        """Initialize or reset monthly balance for a user using custom aic_balance if available"""
        conn = None
        cursor = None
        try:
            conn = DatabaseService.get_connection()
            cursor = conn.cursor()
    
            # Check if user exists and get their aic_balance and scope
            cursor.execute("SELECT id, scope, aic_balance FROM users WHERE id = ?", [user_id])
            user = cursor.fetchone()
            if not user:
                logger.error(f"User {user_id} not found")
                return False
    
            user_scope = user[1]
            custom_balance = user[2]  # Get the user's custom aic_balance
    
            # Determine which balance to use
            monthly_balance = None
            
            # If user has a custom balance set, use it
            if custom_balance is not None:
                monthly_balance = custom_balance
                logger.info(f"Using custom balance {monthly_balance} for user {user_id}")
            else:
                # Otherwise get scope's monthly balance
                cursor.execute("SELECT monthly_balance FROM scope_balance_config WHERE scope = ?", [user_scope])
                scope_config = cursor.fetchone()
                
                if not scope_config:
                    logger.error(f"No balance config found for scope {user_scope}")
                    # Create a default entry with 100 balance
                    monthly_balance = 100
                    cursor.execute(
                        "INSERT INTO scope_balance_config (scope, monthly_balance, description) VALUES (?, ?, ?)", 
                        [user_scope, monthly_balance, f"Default for scope {user_scope}"]
                    )
                    conn.commit()
                else:
                    monthly_balance = scope_config[0]
    
            # Get or create balance record for current month
            current_month = BalanceService.get_first_day_of_month()
            
            # Check if balance already exists for this month
            cursor.execute(
                "SELECT id, current_balance FROM user_balances WHERE user_id = ? AND balance_month = ?",
                [user_id, current_month]
            )
            existing_balance = cursor.fetchone()
            
            if existing_balance:
                # Record exists, no need to update if already initialized
                logger.info(f"Balance already exists for user {user_id} for {current_month}")
                return True
            else:
                # Create new balance record with custom or scope-based balance
                cursor.execute(
                    """
                    INSERT INTO user_balances (user_id, balance_month, current_balance, last_updated)
                    VALUES (?, ?, ?, DATEADD(HOUR, 2, GETUTCDATE()))
                    """,
                    [user_id, current_month, monthly_balance]
                )
                conn.commit()
                logger.info(f"Created new balance of {monthly_balance} for user {user_id} for {current_month}")
                return True
    
        except Exception as e:
            logger.error(f"Error initializing monthly balance: {str(e)}")
            if conn:
                conn.rollback()
            return False
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
        
    @staticmethod
    def check_and_deduct_balance(user_id, endpoint_id, deduction_amount=None):
        """Check if user has sufficient balance and deduct if they do"""
        conn = None
        cursor = None
        try:
            logger.info(f"Checking balance for user {user_id}, endpoint {endpoint_id}")
            conn = DatabaseService.get_connection()
            cursor = conn.cursor()

            # If deduction_amount is not provided, get it from endpoint's cost
            if deduction_amount is None:
                cursor.execute("SELECT cost FROM endpoints WHERE id = ?", [endpoint_id])
                endpoint_result = cursor.fetchone()
                if not endpoint_result:
                    logger.error(f"Endpoint {endpoint_id} not found")
                    return False, "Endpoint not found"
                    
                # Convert to float for consistent handling
                deduction_amount = float(endpoint_result[0])
                logger.info(f"Using endpoint cost of {deduction_amount} for endpoint {endpoint_id}")
            else:
                # Ensure deduction_amount is a float even if provided externally
                deduction_amount = float(deduction_amount)

            current_month = BalanceService.get_first_day_of_month()

            # First, ensure the user has a balance for current month
            initialized = BalanceService.initialize_monthly_balance(user_id)
            if not initialized:
                logger.error(f"Failed to initialize balance for user {user_id}")
                return False, "Failed to initialize balance"

            # Get current balance
            cursor.execute("""
                SELECT current_balance
                FROM user_balances
                WHERE user_id = ? AND balance_month = ?
            """, [user_id, current_month])

            balance_result = cursor.fetchone()
            if not balance_result:
                logger.error(f"No balance record found for user {user_id} for {current_month}")
                return False, "No balance record found"

            # Convert to float for consistent handling
            current_balance = float(balance_result[0])
            logger.info(f"Current balance for user {user_id}: {current_balance}")

            if current_balance < deduction_amount:
                logger.warning(f"Insufficient balance for user {user_id}: {current_balance} < {deduction_amount}")
                return False, "Insufficient balance"

            # Deduct balance and log transaction
            new_balance = current_balance - deduction_amount
            
            cursor.execute("""
                UPDATE user_balances
                SET current_balance = ?,
                    last_updated = DATEADD(HOUR, 2, GETUTCDATE())
                WHERE user_id = ? AND balance_month = ?
            """, [new_balance, user_id, current_month])

            # Log the transaction
            cursor.execute("""
                INSERT INTO balance_transactions 
                (id, user_id, endpoint_id, deducted_amount, balance_after)
                VALUES (NEWID(), ?, ?, ?, ?)
            """, [user_id, endpoint_id, deduction_amount, new_balance])

            conn.commit()
            logger.info(f"Successfully deducted {deduction_amount} from user {user_id}, new balance: {new_balance}")
            return True, new_balance

        except Exception as e:
            logger.error(f"Error checking/deducting balance: {str(e)}")
            if conn:
                conn.rollback()
            return False, str(e)
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
            
    @staticmethod
    def get_current_balance(user_id):
        """Get current balance for a user"""
        conn = None
        cursor = None
        try:
            # Ensure user has current month's balance initialized
            initialized = BalanceService.initialize_monthly_balance(user_id)
            if not initialized:
                return None, "Failed to initialize balance"

            conn = DatabaseService.get_connection()
            cursor = conn.cursor()

            current_month = BalanceService.get_first_day_of_month()

            cursor.execute("""
                SELECT ub.current_balance, u.scope, sbc.description
                FROM user_balances ub
                JOIN users u ON ub.user_id = u.id
                LEFT JOIN scope_balance_config sbc ON u.scope = sbc.scope
                WHERE ub.user_id = ? AND ub.balance_month = ?
            """, [user_id, current_month])

            result = cursor.fetchone()
            if not result:
                return None, "Balance not found"

            scope_description = result[2] if result[2] else f"Scope {result[1]}"

            return {
                "current_balance": result[0],
                "scope": result[1],
                "tier_description": scope_description,
                "month": current_month.strftime("%B %Y")
            }, None

        except Exception as e:
            logger.error(f"Error getting current balance: {str(e)}")
            return None, str(e)
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    @staticmethod
    def update_user_balance(user_id, new_balance):
        """Update user's current balance (admin only)"""
        conn = None
        cursor = None
        try:
            # Validate user exists
            conn = DatabaseService.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("SELECT id FROM users WHERE id = ?", [user_id])
            if not cursor.fetchone():
                return False, f"User {user_id} not found"
            
            current_month = BalanceService.get_first_day_of_month()

            # Check if balance record exists
            cursor.execute("""
                SELECT id FROM user_balances
                WHERE user_id = ? AND balance_month = ?
            """, [user_id, current_month])
            
            if cursor.fetchone():
                # Update existing record
                cursor.execute("""
                    UPDATE user_balances
                    SET current_balance = ?,
                        last_updated = DATEADD(HOUR, 2, GETUTCDATE())
                    WHERE user_id = ? AND balance_month = ?
                """, [new_balance, user_id, current_month])
            else:
                # Create new record
                cursor.execute("""
                    INSERT INTO user_balances (user_id, balance_month, current_balance)
                    VALUES (?, ?, ?)
                """, [user_id, current_month, new_balance])

            conn.commit()
            logger.info(f"Successfully updated balance for user {user_id} to {new_balance}")
            return True, None

        except Exception as e:
            logger.error(f"Error updating balance: {str(e)}")
            if conn:
                conn.rollback()
            return False, str(e)
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
