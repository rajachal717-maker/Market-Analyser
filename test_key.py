from supabase import create_client

url = "https://zthirxdbxhdjfpbcpqmk.supabase.co"
key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRwaGl2dGphcWllaHlvYWlmc3ZmIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODQ4NzQ3NzQsImV4cCI6MjEwMDQ1MDc3NH0.pWzNxv4PZFlHcGghvwOdRlcOJY_JWTwyZA2vZ25bLUg"

print("Connecting to Supabase...")
try:
    supabase = create_client(url, key)
    # Attempt a dummy fake login to test the key
    supabase.auth.sign_in_with_password({"email": "fake@email.com", "password": "fake_password"})
except Exception as e:
    print(f"ERROR RETURNED: {e}")