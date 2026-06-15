# Python FastAPI Fintech Backend: Codebase Structure & Architecture Guide

This guide outlines the layout, design decisions, database models, Pydantic schemas, and endpoints currently implemented in your backend application.

---

## 1. Project Directory Structure

```text
D:\Projects\Backend_learning\
├── database.py       # SQLAlchemy engine, session maker, and Base model
├── models.py         # SQLAlchemy ORM Database tables (PostgreSQL)
├── schema.py         # Pydantic schemas for request/response validation
├── utils.py          # Cryptography helper functions (Bcrypt, JWT)
├── main.py           # FastAPI application startup, routers, and business logic
└── venv\             # Python virtual environment (ignored by Git)
```

---

## 2. File-by-File Responsibilities

### 🔗 `database.py` (The Connection Layer)
Manages the communication channel between your Python code and the PostgreSQL database.
* **`Database_URL`**: The connection string containing the username, password (`Msg@1024`), host, port (`5432`), and database name (`backend`).
* **`engine`**: The active driver that physically communicates with PostgreSQL.
* **`SessionLocal`**: A factory for generating database sessions. Each request gets its own session to query and commit data.
* **`Base`**: The declarative base class. All SQLAlchemy models inherit from this class so they are registered in the metadata catalog.

### 🗄️ `models.py` (The Database Layer)
Defines how tables are structured inside PostgreSQL. This file represents the **physical database schema**.
* **`user_accounts`**: A helper table (Junction/Association Table) representing the Many-to-Many link between users and shared accounts.
* **`User` class**: Represents the `users` table.
* **`Account` class**: Represents the `accounts` table.
* **Relationships**:
  * **One-to-Many**: `User.accounts` $\leftrightarrow$ `Account.owner` (Primary Ownership).
  * **Many-to-Many**: `User.shared_accounts` $\leftrightarrow$ `Account.co_owners` (Shared/Joint Ownership, mapped via the `user_accounts` table).

### 🛡️ `schema.py` (The Validation Layer)
Defines how data enters and leaves the API. These are Pydantic schemas that perform **runtime type checking, serialization, and filtering**.
* **`UserBase`**: Contains common fields for users (`name`, `email`).
* **`UserCreate`**: Inherits from `UserBase` and adds `password` (only used when a user registers).
* **`UserShort`**: A stripped-down user schema (contains `id`, `name`, `email`, `is_active`) to prevent circular references in nested JSON outputs.
* **`User`**: The full response schema sent back to clients. It includes lists of individual `accounts` and `shared_accounts`.
* **`AccountBase`**: Contains common fields for accounts (`account_number`, `balance`, `account_type`).
* **`AccountCreate`**: Used for account creation payloads.
* **`Account`**: The full response schema for accounts, including the list of its `co_owners`.

### 🔑 `utils.py` (The Security Layer)
Handles cryptographic operations to secure credentials and verify identities.
* **Password Hashing**: Uses `passlib` with `bcrypt` to securely hash passwords before storing them, and to verify plain text passwords during login.
* **JWT tokens**: Handles generating JSON Web Tokens (`create_access_tokens`) and decoding/verifying them (`verify_access_tokens`).

### ⚙️ `main.py` (The Routing & Orchestration Layer)
The entry point of the API. It coordinates incoming HTTP requests, performs validations, queries the database, and returns JSON responses.
* **`models.Base.metadata.create_all(bind=database.engine)`**: Runs at startup to create tables in PostgreSQL if they don't exist.
* **`get_db()`**: A dependency function that opens a database session when a request starts and guarantees it closes when the request ends.
* **`get_current_user()`**: An authentication dependency. It extracts the JWT token, decodes it, retrieves the user from the database, and injects the user object into protected endpoints.

---

## 3. API Endpoints Reference

Here is a categorized list of all endpoints implemented in your backend:

| Category | HTTP Method | Route | Description | Auth Required? |
| :--- | :--- | :--- | :--- | :--- |
| **Authentication** | `POST` | `/token` | Authenticates email + password; returns JWT token. | No |
| **Users** | `POST` | `/users` | Registers a new user (hashes password). | No |
| **Users** | `GET` | `/users` | Lists all users in the system. | No |
| **Users** | `GET` | `/users/me` | Fetches the authenticated user's profile and accounts. | **Yes** (JWT Bearer) |
| **Accounts** | `POST` | `/users/{user_id}/accounts` | Creates an individual account for a specific user. | No |
| **Accounts** | `GET` | `/accounts` | Lists all bank accounts in the system. | No |
| **Accounts** | `POST` | `/accounts/{account_id}/add_co_owner/{user_id}` | Links a user as a joint/co-owner to an account (M:N). | No |

---

## 4. Key Distinctions in Code

### 🔀 SQLAlchemy Models vs. Pydantic Schemas

One of the most important concepts in FastAPI is the separation of database models and request/response schemas:

| Attribute | SQLAlchemy Model (`models.py`) | Pydantic Schema (`schema.py`) |
| :--- | :--- | :--- |
| **Purpose** | Map python classes to database rows. | Validate input payloads and format API responses. |
| **Base Class** | Inherits from `Base` (SQLAlchemy). | Inherits from `BaseModel` (Pydantic). |
| **Types** | Uses database types (e.g. `Column`, `Integer`, `String`, `Numeric(10,2)`). | Uses Python type annotations (e.g. `int`, `str`, `float`, `List[Account]`). |
| **Behavior** | Used for reading/writing to the database. | Used for input serialization and response styling. |

### 🔤 Singular vs. Plural Variable Names in Code

When writing backend logic, pay close attention to capitalization and pluralization:

* **`models.User` (Capital, Singular)**: The database model class. Used for querying (e.g. `db.query(models.User)`) or instantiating a database row.
* **`schema.User` (Capital, Singular)**: The Pydantic response schema class. Used in endpoint signatures as a response type (e.g. `response_model=schema.User`).
* **`user` (Lowercase, Singular)**: Typically represents a single object/record. For example:
  * An input parameter in FastAPI representing a request body: `user: schema.UserCreate`.
  * A single queried database record: `user = db.query(models.User)...first()`.
* **`users` (Lowercase, Plural)**:
  * The database table name: `__tablename__ = "users"`.
  * A route path prefix: `@app.get("/users")`.

### 🔄 Resolving Circular Schema References (`UserShort` vs `User` vs `Account`)

Because a user can own multiple accounts, and an account can have multiple co-owning users, we have a bidirectional relationship:
* `User` $\rightarrow$ contains `Account`
* `Account` $\rightarrow$ contains `User`

If we used the full schemas for both, Pydantic would get stuck in an infinite serialization loop:
`User` $\rightarrow$ `Account` $\rightarrow$ `User` $\rightarrow$ `Account` $\dots$

To break this circle, we created **`UserShort`**:
1. `User` contains a list of full `Account`s.
2. `Account` contains a list of **`UserShort`**s (which only contain `id`, `name`, `email`, `is_active` and **do not** contain any list of accounts).
This halts the chain and returns a clean, nested JSON structure.
