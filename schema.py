from pydantic import BaseModel, EmailStr
from typing import List,Optional

# ==================== USER BASE & SHORT SCHEMAS ====================

# Base: Commmon fields for all users
class UserBase(BaseModel):
    name : str
    email : EmailStr

# Simplified User represenation to prevent circular references 
class UserShort(UserBase):
    id : int
    is_active : bool
    class Config:
        from_attributes = True

# ==================== ACCOUNT SCHEMAS ====================

# Accounts Schema
class AccountBase(BaseModel):
    account_number : str
    balance : float = 0.00
    account_type : str

# To Create an Account
class AccountCreate(AccountBase):
    pass # Everything is already defined in AccountBase

# To See an Account
class Account(AccountBase):
    id : int
    owner_id : int
    co_owners: List[UserShort] = []

    class Config:
        from_attributes = True

# ==================== USER SCHEMAS (FULL) ====================

# To Create : What we need from the User(includes password)
class UserCreate(UserBase):
    password : str

# To See : What we send back to the User
class User(UserBase):
    id : int
    is_active : bool
    
    # MAGIC LINE: Allows us to load the "accounts" list
    accounts: List[Account] = []
    shared_accounts: List[Account] = []

    class Config:
        from_attributes = True


# ==================== AUTH SCHEMAS ====================

# Token response Schema
class Token(BaseModel):
    access_token : str
    token_type : str

# Schema for token payload extraction
class TokenData(BaseModel):
    email: Optional[str] = None

# ==================== TRANSFER SCHEMAS ====================

class TransferCreate(BaseModel):
    sender_account_id: int
    receiver_account_id: int
    amount: float