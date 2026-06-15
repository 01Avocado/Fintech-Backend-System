import multiprocessing
from fastapi.dependencies.utils import multipart_not_installed_error
import asyncio
from fastapi import FastAPI, Depends, HTTPException,status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
import time
from decimal import Decimal
import os
import multiprocessing
import models, schema, database, utils

# Create the Database Tables
models.Base.metadata.create_all(bind=database.engine1)
models.Base.metadata.create_all(bind=database.engine2)

app=FastAPI()

# Mount the static frontend folder for CSS/JS
app.mount("/static", StaticFiles(directory="frontend"), name="static")

# Serve index.html at root route
@app.get("/", response_class=HTMLResponse)
def read_root():
    index_path = os.path.join("frontend", "index.html")
    if not os.path.exists(index_path):
        return "Frontend files not found. Creating..."
    with open(index_path, "r") as f:
        return f.read()

# Define the origins that are allowed to make requests (your frontend URL)
origins = [
    "http://localhost:3000",  # React local dev server
    "https://your-frontend-domain.com",  # Production frontend URL
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],  # Allow GET, POST, PUT, DELETE, etc.
    allow_headers=["*"],  # Allow all headers (including Authorization header for JWT tokens)
)



oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# The "Get_DB" Dependency
def get_db(shard_key: int = 1):
    if shard_key % 2 == 1:
        db = database.SessionLocal1()
        print(f"\n[SHARD ROUTER] Routing request to Shard 1 (Database: backend) for Key: {shard_key}\n")
    else:
        db = database.SessionLocal2()
        print(f"\n[SHARD ROUTER] Routing request to Shard 2 (Database: backend_shard2) for Key: {shard_key}\n")
    try:
        yield db
    finally:
        db.close()
        
# The POST API (Create User)
@app.post("/users",response_model=schema.User)
def create_user(user : schema.UserCreate, db: Session = Depends(get_db)):
    # check if user already exists
    db_user = db.query(models.User).filter(models.User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create the new user
    plain_password = user.password
    hashed_password = utils.hash_password(plain_password) 
    new_user = models.User(name = user.name,email = user.email, password = hashed_password)
    db.add(new_user)
    db.commit() # Saves everything
    db.refresh(new_user) # Get the new ID from the DB

    return new_user

# The GET API (Everyone Sees)
@app.get("/users",response_model=list[schema.User])
def read_users(db: Session = Depends(get_db)):
    return db.query(models.User).all()

# Create an Account for a SPECIFIC user
@app.post("/users/{user_id}/accounts",response_model=schema.Account)
def create_account(user_id: int, account : schema.AccountCreate, db: Session= Depends(get_db)):
    # First check if the user exists
    db_account = db.query(models.Account).filter(models.Account.account_number == account.account_number).first()
    if db_account:
        raise HTTPException(status_code=400,details="User not found")

    # Create New Account  
    new_account = models.Account(owner_id = user_id, **account.dict())
    db.add(new_account)
    db.commit()
    db.refresh(new_account)
    return new_account

# See all the Accounts in the system
@app.get("/accounts",response_model=list[schema.Account])
def read_accounts(db: Session= Depends(get_db)):
    return db.query(models.Account).all()

@app.post("/token")
def login(user_credentials: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    # Find the User
    user = db.query(models.User).filter(models.User.email == user_credentials.username).first()
    # Check if the user exists
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail = "Invalid Credentials"
        )
    # Verify the password
    is_valid = utils.verify_password(user_credentials.password, user.password)
    if not is_valid:
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED,
            detail = "Invalid Credentials"
        )
    # Generate access Token
    access_token = utils.create_access_tokens(data= {"sub": user.email})
    return {"access_token" : access_token, "token_type" : "bearer"}

def get_current_user(token: str = Depends(oauth2_scheme),db: Session = Depends(get_db)):
    # Preconfigure the exception to rause if auth fails
    credentials_exception = HTTPException(
        status_code = status.HTTP_401_UNAUTHORIZED,
        detail = "Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    # Decode the JWT Token
    email = utils.verify_access_tokens(token, credentials_exception)
    # Retrieve the user from DB
    user = db.query(models.User).filter(models.User.email == email).first()
    if user is None:
        raise credentials_exception
    return user
    
@app.get("/users/me", response_model = schema.User)
def read_user_me(current_user: models.User = Depends(get_current_user)):
    return current_user

# Add user as a Co owner to an Account (M:N Link)
@app.post("/accounts/{account_id}/add_co_owner/{user_id}",response_model=schema.Account)
def add_co_owner(account_id:int, user_id: int, db : Session = Depends(get_db)):    
    #1 Fetch the account
    account = db.query(models.Account).filter(models.Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail = "Account not found")

    #2 Fetch the user to be added 
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail = "User not found")

    #3 Validation to ensure current user is the owner
    if account.owner_id == user_id:
        raise HTTPException(status_code = 403, detail="User is already the primary owner of this account")

    #4 Validation to Ensure user is not already a co owner
    if user in account.co_owners:
        raise HTTPException(status_code=400, detail = "User is already a co owner")

    #5 Append to the relationship list
    account.co_owners.append(user)
    db.commit()
    db.refresh(account)

    return account

# Blocking Endpoints(hogs the thread, freezes the server)
@app.get("/tests/blocking")
async def test_blocking():
    print("Starting blocking task(5 Secs)...")
    time.sleep(5) #sychronous blocking sleep
    print("blocking task completed!")
    return{"message":"Finished blocking task after 5 secs"}

# Non-Blocking Endpoint(Yield controls, server remains responsive)
@app.get("/tests/non-blocking")
async def test_non_blocking():
    print("Starting non-blocking task...")
    await asyncio.sleep(5) #asynchronous non-blocking sleep
    print("non-blocking task completed!")
    return{"message":"Finished non-blocking task after 5 secs"}

# Bank Transfer Endpoint with Pessimistic Locking and Deadlock Prevention
@app.post("/transfers")
def transfer_funds(transfer : schema.TransferCreate, db : Session = Depends(get_db)):
    # Validation to ensure amount is positive
    if transfer.amount <= 0:
        raise HTTPException(status_code=400, detail="Transfer amount should be greater than zero")

    # Validate the sender and reciever are different accounts
    if transfer.sender_account_id == transfer.receiver_account_id:
        raise HTTPException(status_code=400, detail="Cannot transfer money to the same account")

    # Deadlock Prevention: Determine lock ordering by sorting the IDs (Always lock the smaller id first)
    first_id = min(transfer.sender_account_id, transfer.receiver_account_id)
    second_id = max(transfer.sender_account_id,transfer.receiver_account_id)

    # Fetch the accounts in sorted order using Pessimistic Locking( .with_for_update())
    first_account= db.query(models.Account).filter(models.Account.id == first_id).with_for_update().first()
    second_account = db.query(models.Account).filter(models.Account.id == second_id).with_for_update().first()

    if not first_account or not second_account:
        raise HTTPException(status_code=404, detail="one or both accounts not found")
    
    # Map the locked accounts back to sender and reciever
    if first_account.id == transfer.sender_account_id:
        sender_account = first_account
        receiver_account = second_account
    else:
        sender_account = second_account
        receiver_account = first_account
    
    # Validate if sender has enough balance
    transfer_amount = Decimal(str(transfer.amount))
    if sender_account.balance < transfer_amount:
        raise HTTPException(status_code=400, detail="Insufficient balance")
    
    # Execute Transfer(SQLAlchemy tracks these updates automatically)
    sender_account.balance -= transfer_amount
    receiver_account.balance += transfer_amount

    db.commit() # Saves both updates and Releases all locked rows in PostgreSQL

    return{
        "message": "Transfer completed successfully",
        "sender_account_id": sender_account.id,
        "sender_new_balance": float(sender_account.balance),
        "receiver_account_id": receiver_account.id,
        "receiver_new_balance": float(receiver_account.balance)
    }

# ==================== DISTRIBUTED QUEUE SIMULATION ====================
# The BG Worker Function(runs completely seperate OS process)
def background_worker(queue: multiprocessing.Queue):
    import time
    import os
    from dotenv import load_dotenv

    # Ensure environment variables are loaded in this child process
    load_dotenv()
    
    print("\n[WORKER] Background worker process started and listening for jobs...\n", flush=True)
    while True:
        # Get a task from the Queue(blocks until job is available)
        job = queue.get()

        # Check for "poison spill" to safely shutdown
        if job is None:
            print("\n[WORKER] Worker process shutting down \n", flush=True)
            break

        print(f"\n[WORKER] Received Job: {job['task_name']} for {job['target_email']}", flush=True)
        
        # Check if we have email configured (either Brevo, Resend, or SMTP)
        is_configured = os.getenv("BREVO_API_KEY") or os.getenv("RESEND_API_KEY") or (
            os.getenv("SMTP_HOST") and os.getenv("SMTP_PORT") and 
            os.getenv("SMTP_USER") and os.getenv("SMTP_PASSWORD") and 
            "your-email" not in os.getenv("SMTP_USER", "")
        )
        
        if is_configured:
            try:
                if job["task_name"] == "send welcome email":
                    subject = "Welcome to Antigravity Vault! 🚀"
                    body = (
                        f"Hey there,\n\n"
                        f"Welcome to Antigravity Vault! 🌌 We're absolutely thrilled to have you join our next-generation, high-performance banking experience.\n\n"
                        f"Your secure account has been initialized across our distributed database shards, and you're now ready to perform lightning-fast transfers with complete cryptographic peace of mind.\n\n"
                        f"To help you get started:\n"
                        f"• Explore your glassmorphic user dashboard\n"
                        f"• Try a secure locked transfer\n"
                        f"• Set up your joint co-owner accounts\n\n"
                        f"If you need any guidance or want to geek out over our async systems architecture, we are always here for you.\n\n"
                        f"To the stars and beyond! 💫\n\n"
                        f"Warmly,\n"
                        f"The Antigravity Team"
                    )
                else:
                    subject = f"Antigravity Vault: {job['task_name']} Complete"
                    body = (
                        f"Hello,\n\n"
                        f"Your background task '{job['task_name']}' has been processed successfully by the Antigravity Vault Worker node.\n\n"
                        f"Best regards,\n"
                        f"Antigravity Vault Core"
                    )
                
                # Import utils inside worker to avoid serializing issues during process spawn
                import utils
                print(f"[WORKER] Sending real email notification to {job['target_email']}...", flush=True)
                res = utils.send_email(job["target_email"], subject, body)
                print(f"[WORKER] SUCCESS: {res}!\n", flush=True)
            except Exception as e:
                print(f"[WORKER] Email sending failed: {e}. Falling back to simulation mode...", flush=True)
                time.sleep(4)
                print(f"[WORKER] SUCCESS: Finished Job: {job['task_name']} for {job['target_email']} (simulated)\n", flush=True)
        else:
            print("[WORKER] Email credentials not configured. Running in simulation mode (4 seconds)...", flush=True)
            time.sleep(4)
            print(f"[WORKER] SUCCESS: Finished Job: {job['task_name']} for {job['target_email']} (simulated)\n", flush=True)

# Intialize a thread/process safe Queue
task_queue = multiprocessing.Queue()
worker_process = None

@app.on_event("startup")
def startup_event():
    global worker_process
    worker_process = multiprocessing.Process(target = background_worker, args=(task_queue,))
    worker_process.daemon = True  # Allows process to close when the main server closes
    worker_process.start() # Start the background worker
    print("[MAIN] Background worker process started")

@app.on_event("shutdown")
def studown_event():
    global worker_process
    if worker_process:
        task_queue.put(None) # Send the shutdown signal to the worker
        worker_process.join()

# Endpoint to Enqueue tasks(Producers)
@app.post("/test/enqueue")
def enqueue_task(email:str):
    job_ticket = {
        "task_name" : "send welcome email",
        "target_email" : email
    }

    task_queue.put(job_ticket)
    return {"message": "Job enqueued for background processing","job" : job_ticket}

# Synchronous test endpoint to debug SMTP/Resend settings directly
@app.get("/test/send_email_sync")
def send_email_sync(email: str):
    import utils
    import traceback
    try:
        subject = "Welcome to Antigravity Vault! 🚀"
        body = (
            f"Hey there,\n\n"
            f"Welcome to Antigravity Vault! 🌌 We're absolutely thrilled to have you join our next-generation, high-performance banking experience.\n\n"
            f"Your secure account has been initialized across our distributed database shards, and you're now ready to perform lightning-fast transfers with complete cryptographic peace of mind.\n\n"
            f"To help you get started:\n"
            f"• Explore your glassmorphic user dashboard\n"
            f"• Try a secure locked transfer\n"
            f"• Set up your joint co-owner accounts\n\n"
            f"If you need any guidance or want to geek out over our async systems architecture, we are always here for you.\n\n"
            f"To the stars and beyond! 💫\n\n"
            f"Warmly,\n"
            f"The Antigravity Team"
        )
        result = utils.send_email(email, subject, body)
        return {
            "status": "success",
            "message": result
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "traceback": traceback.format_exc()
        }