# Deployment Troubleshooting Guide

## 1. Project Architecture (Current State)
- **Backend Server:** Deployed live on Render (`https://hostel-hunt-backend.onrender.com`)
- **Database:** Deployed live on Railway (PostgreSQL)
- **Frontend (Admin Panel):** Running locally (`http://localhost:5173`) but configured to communicate with the live Render backend.

*Important Note on Data:* Because your local development environment was connected to the Railway database via your local `.env` variables, all the data you created locally (Owners, Hostels, Media) was actually saved directly to Railway. This means **you do not need to recreate your data** when moving to production!

---

## 2. Connecting the Frontend to the Live Backend
To ensure your local frontend talks to the live server instead of a local backend, you must update the API base URL in your frontend code.

**Files Updated:**
1. `.env` file in the frontend folder:
   ```env
   VITE_API_URL=https://hostel-hunt-backend.onrender.com/api/v1
   ```
2. `src/services/api.ts` fallback:
   ```typescript
   const API_BASE_URL = import.meta.env.VITE_API_URL || 'https://hostel-hunt-backend.onrender.com/api/v1';
   ```

**Result:** When you run `npm run dev` and attempt to log in, the request is sent directly to your Render server.

---

## 3. The "400 Bad Request" (HTML) Error & ALLOWED_HOSTS
When you attempted to log in using the live backend, you received a `400 Bad Request` error. 

**Diagnosing the Error:**
- By inspecting the network request in Chrome DevTools (Network Tab -> Click the `login/` request -> Response Tab), we saw the server returned an **HTML page** instead of a JSON error message.
- Because your backend is an API that communicates in JSON, an HTML response means the request was **blocked by Django's core security system** before it ever reached your custom login code.

**The Cause (`ALLOWED_HOSTS`):**
When Django runs in production (`DEBUG=False`), it implements a strict security measure called `ALLOWED_HOSTS`. It will instantly reject any request if the domain name in the URL (`hostel-hunt-backend.onrender.com`) is not explicitly whitelisted.

**The Solution:**
1. Log into your **Render Dashboard**.
2. Select your Backend Web Service.
3. Navigate to the **Environment** tab.
4. Locate the `ALLOWED_HOSTS` environment variable.
5. Set its value to exactly: `hostel-hunt-backend.onrender.com` (or `*` to allow all traffic temporarily).
6. Save the changes. Render will automatically reboot the server.

Once the server restarts, Django will allow the frontend to communicate with it, and you will be able to log in using your existing accounts stored in Railway.
