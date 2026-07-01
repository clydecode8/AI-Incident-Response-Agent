package com.incident.incident_demo;

public class UserService {

    public void sendWelcomeEmail() {
        LogUtil.info(
                "UserService",
                "Preparing welcome email..."
        );

        User user = findUserById(1001);

        // Intentional code bug:
        // user is null, so this line throws NullPointerException.
        String email = user.getEmail();

        LogUtil.info(
                "UserService",
                "Sending welcome email to " + email
        );
    }

    private User findUserById(int id) {
        LogUtil.info(
                "UserService",
                "Fetching user by id=" + id
        );

        // Simulates a code logic bug: user not found but caller does not check null.
        return null;
    }
}