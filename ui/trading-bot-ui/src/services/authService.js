const API_URL = process.env.REACT_APP_API_URL;

// ✅ Signup API Call
export const signup = async (credentials) => {
    try {
        const response = await fetch(`${API_URL}/api/auth/signup`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(credentials),
        });

        const data = await response.json();

        if (!response.ok) {
            return { 
                success: false, 
                message: Array.isArray(data.detail?.errors) 
                    ? data.detail.errors.join(", ")  // ✅ Properly format multiple errors
                    : data.detail || "Signup failed"
            };
        }

        return { success: true, message: "Signup successful" };
    } catch (error) {
        return { success: false, message: "Server error. Please try again later." };
    }
};

// ✅ OTP Verification API Call
export const verifyOtp = async (phone, countryCode, otp) => {
    try {
        const response = await fetch(`${API_URL}/api/auth/verify-otp`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ phone_number: phone, country_code: countryCode, otp }),
        });

        const data = await response.json();

        if (!response.ok) {
            return { 
                success: false, 
                message: data.detail === "OTP has expired. Please request a new one."
                    ? "Your OTP has expired. Please request a new one."
                    : data.detail || "OTP verification failed."
            };
        }

        return { success: true, message: data.message };
    } catch (error) {
        return { success: false, message: "Server error. Please try again later." };
    }
};

// ✅ Resend OTP API Call
export const resendOtp = async (phone_number, country_code) => {
    try {
        const response = await fetch(`${API_URL}/api/auth/resend-otp`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ phone_number, country_code }),
        });

        return await response.json();
    } catch (error) {
        console.error("Resend OTP Error:", error);
        return { success: false, message: "Failed to resend OTP" };
    }
};

// ✅ Login API Call (Handles Email & Phone Login)
export const login = async (credentials) => {
    try {
        const response = await fetch(`${API_URL}/api/auth/login`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(credentials)
        });

        const data = await response.json();
        console.log("🔴 API Response:", data);

        if (!response.ok) {
            return { success: false, message: data.detail || "Login failed" };
        }

        // ✅ Store access token correctly
        localStorage.setItem("access_token", data.access_token);
        localStorage.setItem("refresh_token", data.refresh_token);
        localStorage.setItem("isLoggedIn", "true");
        window.dispatchEvent(new Event("storage"));
        return { success: true, message: data.message };
    } catch (error) {
        console.error("🔴 Login Request Failed:", error);
        return { success: false, message: "Server error. Please try again later." };
    }
};

// ✅ Logout Function
export const logout = () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    localStorage.removeItem("isLoggedIn");
    window.location.href = "/";
};

// ✅ Check if User is Authenticated
export const isAuthenticated = () => !!localStorage.getItem("access_token");

// ✅ API Request with Authentication & Auto Token Refresh
export const fetchWithAuth = async (url, options = {}) => {
    try {
        const response = await fetch(url, {
            ...options,
            credentials: "include", // ✅ Ensure cookies are sent
        });

        if (response.status === 401) {
            console.warn("🔄 Access token expired! Refreshing...");
            // Fix: Use refreshAccessToken instead of undefined refreshToken
            const newToken = await refreshAccessToken();
            if (!newToken) {
                console.error("❌ Token refresh failed");
                logout(); // Redirect to login if refresh fails
                return null;
            }
            // Retry the request with new token
            return fetch(url, { 
                ...options, 
                credentials: "include",
                headers: {
                    ...options.headers,
                    Authorization: `Bearer ${newToken}`
                }
            });
        }

        return response.json();
    } catch (error) {
        console.error("❌ API request failed:", error);
        return null;
    }
};

export const refreshAccessToken = async () => {
    const refreshToken = localStorage.getItem("refresh_token");

    if (!refreshToken) {
        console.warn("No refresh token found.");
        return null;
    }

    try {
        const response = await fetch(`${API_URL}/api/auth/refresh-token`, {
            method: "POST",
            headers: {
                "Refresh-Token": refreshToken,
                "Content-Type": "application/json",
            },
            credentials: "include",
        });

        if (!response.ok) {
            console.warn("Refresh token failed.");
            return null;
        }

        const data = await response.json();
        localStorage.setItem("access_token", data.access_token);
        return data.access_token;
    } catch (error) {
        console.error("Token refresh error:", error);
        return null;
    }
};


export const getAccessToken = () => localStorage.getItem("access_token");
export const getRefreshToken = () => localStorage.getItem("refresh_token");

export const setAccessToken = (token) => localStorage.setItem("access_token", token);
export const setRefreshToken = (token) => localStorage.setItem("refresh_token", token);

export const clearTokens = () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
};
