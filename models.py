from database import Base
from sqlalchemy.orm import relationship
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Numeric, Table

# Association Table for Shared acc access (M:N relation)
user_accounts = Table(
 "user_accounts",
 Base.metadata,
 Column("user_id", Integer,ForeignKey("users.id",ondelete="CASCADE"),primary_key=True),
 Column("account_id", Integer,ForeignKey("accounts.id",ondelete="CASCADE"),primary_key=True, index=True),   
)

class User(Base):
    __tablename__ = "users"
    id = Column(Integer,primary_key=True,index=True)
    name = Column(String)
    email = Column(String, unique = True, index=True)
    password = Column(String)
    is_active = Column(Boolean, default=True)

    # The SHORTCUT: Link backs to accounts table
    accounts = relationship("Account", back_populates = "owner")
    shared_accounts = relationship("Account",secondary=user_accounts,back_populates="co_owners")

class Account(Base):
    __tablename__="accounts"
    id = Column(Integer,primary_key=True, index = True)
    account_number = Column(String, unique= True, index=True)
    balance = Column(Numeric(10,2),default = 0.00)
    account_type = Column(String)
    owner_id = Column(Integer, ForeignKey("users.id"), index =True)

    # The SHORTCUT: Link back to user
    owner = relationship("User", back_populates = "accounts")
    co_owners = relationship("User",secondary=user_accounts,back_populates="shared_accounts")
