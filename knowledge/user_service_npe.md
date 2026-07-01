# UserService NullPointerException Runbook

UserService is responsible for user profile lookup and welcome email delivery.

Common NullPointerException causes:
- User record not found
- Missing null check before accessing user profile
- Downstream user lookup returns null
- Invalid user ID or missing test data

Recommended investigation steps:
1. Check UserService logs.
2. Identify the method where NullPointerException occurred.
3. Verify whether findUserById returned null.
4. Add null handling before calling user.getEmail().
5. Return a controlled error instead of allowing runtime exception.