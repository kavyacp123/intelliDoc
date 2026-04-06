from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from authlib.integrations.starlette_client import OAuth, OAuthError
from app.core.config import settings
from app.core.database import get_connection
from app.core.security import create_access_token
import uuid
import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Google Authentication"])

# Initialize OAuth registry
oauth = OAuth()
oauth.register(
    name='google',
    client_id=settings.GOOGLE_CLIENT_ID,
    client_secret=settings.GOOGLE_CLIENT_SECRET,
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={
        'scope': 'openid email profile'
    }
)

@router.get("/auth/google")
async def login_google(request: Request):
    """Redirect user to Google log in page."""
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth2 is not configured in .env"
        )
    
    redirect_uri = request.url_for('auth_google_callback')
    return await oauth.google.authorize_redirect(request, redirect_uri)

@router.get("/auth/google/callback", name="auth_google_callback")
async def auth_google_callback(request: Request):
    """Handle callback from Google. Verify tokens and issue JWT."""
    try:
        token = await oauth.google.authorize_access_token(request)
    except OAuthError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Google authentication failed: {error.error}"
        )
    
    user_info = token.get('userinfo')
    if not user_info:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to retrieve user info from Google"
        )
    
    email = user_info.get('email')
    google_id = user_info.get('sub')
    
    if not email or not google_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google account missing required identifying info"
        )

    conn = get_connection()
    
    # 1. Try to find user by google_id
    user = conn.execute(
        "SELECT user_id FROM users WHERE google_id = ?",
        [google_id]
    ).fetchone()

    if not user:
        # 2. Try to link existing email user to google_id
        existing_email = conn.execute(
            "SELECT user_id FROM users WHERE email = ?",
            [email]
        ).fetchone()
        
        if existing_email:
            user_id = existing_email[0]
            conn.execute(
                "UPDATE users SET google_id = ? WHERE user_id = ?",
                [google_id, user_id]
            )
            logger.info(f"Linked existing email user {email} to Google ID {google_id}")
        else:
            # 3. Create new user
            user_id = str(uuid.uuid4())
            conn.execute(
                "INSERT INTO users (user_id, email, google_id) VALUES (?, ?, ?)",
                [user_id, email, google_id]
            )
            logger.info(f"Created new Google user for email {email}")
    else:
        user_id = user[0]

    # 4. Issue JWT
    jwt_token = create_access_token(data={"sub": user_id})
    
    # In a real app, you might want to redirect to a specific frontend URL with the token
    # For now, we'll return it as JSON or redirect to a success page.
    # Frontend will typically handle this by grabbing the token from the query params or a cookie.
    
    # Example: redirect to frontend dashboard with token
    frontend_url = "http://localhost:5173" # Update as needed
    return RedirectResponse(url=f"{frontend_url}/auth-callback?token={jwt_token}")
