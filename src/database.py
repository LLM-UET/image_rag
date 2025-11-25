"""
Database connection and ORM models for MySQL
Uses SQLAlchemy for database operations
"""
import os
from typing import Optional
from datetime import datetime

from sqlalchemy import (
    create_engine, Column, Integer, String, Text, JSON, 
    TIMESTAMP, DECIMAL, Enum as SQLEnum, ForeignKey, Table
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from sqlalchemy.sql import func

from config.settings import settings

# Database connection configuration
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT = os.getenv("MYSQL_PORT", "3306")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "telco_db")

# Create connection string
DATABASE_URL = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}?charset=utf8mb4"

# Create engine
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,  # Verify connections before using
    pool_recycle=3600,   # Recycle connections after 1 hour
    echo=False           # Set to True for SQL query logging
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for ORM models
Base = declarative_base()


# ============================================================================
# ORM Models
# ============================================================================

# Junction table for Employee-Role M-to-N
employee_roles = Table(
    'employee_roles',
    Base.metadata,
    Column('employee_id', Integer, ForeignKey('employees.id', ondelete='CASCADE'), primary_key=True),
    Column('role_id', Integer, ForeignKey('roles.id', ondelete='CASCADE'), primary_key=True),
    Column('assigned_at', TIMESTAMP, server_default=func.current_timestamp())
)

# Junction table for Role-Permission M-to-N
role_permissions = Table(
    'role_permissions',
    Base.metadata,
    Column('role_id', Integer, ForeignKey('roles.id', ondelete='CASCADE'), primary_key=True),
    Column('permission_id', Integer, ForeignKey('permissions.id', ondelete='CASCADE'), primary_key=True),
    Column('assigned_at', TIMESTAMP, server_default=func.current_timestamp())
)

# Junction table for Customer-Package M-to-N
customer_packages = Table(
    'customer_packages',
    Base.metadata,
    Column('customer_id', Integer, ForeignKey('customers.id', ondelete='CASCADE'), primary_key=True),
    Column('package_id', Integer, ForeignKey('packages.id', ondelete='CASCADE'), primary_key=True),
    Column('subscribed_at', TIMESTAMP, server_default=func.current_timestamp()),
    Column('expires_at', TIMESTAMP, nullable=True),
    Column('status', SQLEnum('active', 'expired', 'cancelled', name='subscription_status'), default='active')
)


class Employee(Base):
    """Employee model - System operators"""
    __tablename__ = 'employees'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False)
    password = Column(String(255), nullable=False)
    full_name = Column(String(255))
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    
    # Relationships
    roles = relationship("Role", secondary=employee_roles, back_populates="employees")


class Role(Base):
    """Role model - Job titles/groups"""
    __tablename__ = 'roles'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    
    # Relationships
    employees = relationship("Employee", secondary=employee_roles, back_populates="roles")
    permissions = relationship("Permission", secondary=role_permissions, back_populates="roles")


class Permission(Base):
    """Permission model - Access rights"""
    __tablename__ = 'permissions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    
    # Relationships
    roles = relationship("Role", secondary=role_permissions, back_populates="permissions")


class Faq(Base):
    """FAQ model - Knowledge base"""
    __tablename__ = 'faqs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())


class Package(Base):
    """Package model - Telecommunication plans"""
    __tablename__ = 'packages'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False)
    package_data = Column('metadata', JSON)  # Map to 'metadata' column in DB, use 'package_data' in Python
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    
    # Relationships
    customers = relationship("Customer", secondary=customer_packages, back_populates="packages")


class PackageMetadataInterpretation(Base):
    """Package metadata field definitions for AI reasoning"""
    __tablename__ = 'package_metadata_interpretations'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    field_name = Column(String(100), unique=True, nullable=False)
    field_local_name = Column(String(255))
    field_interpretation = Column(Text)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())


class Customer(Base):
    """Customer model - End users"""
    __tablename__ = 'customers'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    full_name = Column(String(255))
    phone_number = Column(String(20), unique=True, nullable=False)
    status = Column(SQLEnum('inactive', 'active', 'suspended', 'cancelled', name='customer_status'), default='active')
    balance = Column(DECIMAL(15, 2), default=0.00)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    
    # Relationships
    packages = relationship("Package", secondary=customer_packages, back_populates="customers")
    chats = relationship("CSChat", back_populates="customer")


class CSChat(Base):
    """CS Chat session model"""
    __tablename__ = 'cs_chats'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(Integer, ForeignKey('customers.id', ondelete='CASCADE'), nullable=False)
    type = Column(SQLEnum('TEXT', 'AUDIO', name='chat_type'), nullable=False)
    summary = Column(Text)
    customer_satisfaction = Column(
        SQLEnum('UNKNOWN', 'EXCELLENT', 'GOOD', 'NEUTRAL', 'BAD', 'TERRIBLE', name='satisfaction_level'),
        default='UNKNOWN'
    )
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    
    # Relationships
    customer = relationship("Customer", back_populates="chats")
    messages = relationship("CSChatMessage", back_populates="chat")


class CSChatMessage(Base):
    """CS Chat message model"""
    __tablename__ = 'cs_chat_messages'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    cs_chat_id = Column(Integer, ForeignKey('cs_chats.id', ondelete='CASCADE'), nullable=False)
    text_content = Column(Text, nullable=False)
    emotion = Column(String(50))
    sender = Column(SQLEnum('EMPLOYEE', 'CUSTOMER', name='sender_type'), nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    
    # Relationships
    chat = relationship("CSChat", back_populates="messages")


# ============================================================================
# Database utilities
# ============================================================================

def get_db():
    """
    Dependency for FastAPI endpoints.
    Yields database session and ensures cleanup.
    
    Usage:
        @app.get("/packages")
        def list_packages(db: Session = Depends(get_db)):
            packages = db.query(Package).all()
            return packages
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Initialize database tables.
    Creates all tables defined in Base metadata.
    """
    Base.metadata.create_all(bind=engine)
    print("Database tables created successfully!")


def test_connection():
    """Test database connection"""
    try:
        db = SessionLocal()
        db.execute("SELECT 1")
        db.close()
        print(f"✓ Connected to MySQL database: {MYSQL_DATABASE}")
        return True
    except Exception as e:
        print(f"✗ Database connection failed: {e}")
        return False


if __name__ == "__main__":
    # Test connection
    print("Testing MySQL connection...")
    print(f"Host: {MYSQL_HOST}:{MYSQL_PORT}")
    print(f"Database: {MYSQL_DATABASE}")
    print(f"User: {MYSQL_USER}")
    print()
    
    if test_connection():
        # Initialize tables
        response = input("Create/update database tables? (y/n): ")
        if response.lower() == 'y':
            init_db()
    else:
        print("\nPlease check your MySQL configuration:")
        print("1. Ensure MySQL server is running")
        print("2. Create database: CREATE DATABASE telco_db;")
        print("3. Set environment variables:")
        print("   - MYSQL_USER")
        print("   - MYSQL_PASSWORD")
        print("   - MYSQL_HOST")
        print("   - MYSQL_PORT")
        print("   - MYSQL_DATABASE")
