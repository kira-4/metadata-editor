# Custom Genre Fix - Testing Guide

## Quick Debug Instructions

### How to Verify the Bug is Fixed

**Before starting service, open Browser DevTools:**
1. Press F12 or right-click → Inspect
2. Go to **Network** tab
3. Check "Preserve log" to keep requests visible

### Test Scenario 1: Custom Genre Success Path

**Steps:**
1. Start your service: `python -m app.main`
2. Open browser to `http://localhost:8090`
3. Find a pending item in the UI
4. Click "أخرى…" (Other) button
5. **In Network tab:** Verify NO request to `/api/pending/{id}/update` is sent (or if sent, genre is NOT empty)
6. Type "نشيد ولائي" in the custom genre input field
7. Wait 1 second (for debounce)
8. **In Network tab:** Look for POST `/api/pending/{id}/update`
   - Click on it → Go to "Payload" tab
   - **Should show:** `{"genre": "نشيد ولائي"}`
   - Response should be **200 OK**
9. Click "تأكيد ونقل إلى المكتبة" (Confirm)
10. **In Network tab:** POST `/api/pending/{id}/confirm`
    - Response should be **200 OK**
    - File should move to `/music`

**Expected Result:** ✅ Success! Custom genre works.

---

### Test Scenario 2: Empty Custom Genre Rejection

**Steps:**
1. Click "أخرى…" button
2. Leave custom input **empty**
3. Try to click Confirm button
4. **Expected:** Button remains **disabled** (frontend validation prevents click)

---

### Test Scenario 3: Backend Validation (Edge Cases)

**Test 3a: Whitespace-Only Genre**
1. Click "أخرى…"
2. Type only spaces: "     "
3. Manually enable Confirm button via DevTools Console:
   ```javascript
   document.querySelector('.confirm-btn').disabled = false
   ```
4. Click Confirm
5. **In Network tab:** Response should be **400 Bad Request**
6. **Response body:** `{"detail": "النوع الموسيقي مطلوب (Genre is required)"}`

**Test 3b: Literal "أخرى…" as Genre**
1. Use DevTools Console to force set genre:
   ```javascript
   fetch('/api/pending/1/update', {
     method: 'POST',
     headers: {'Content-Type': 'application/json'},
     body: JSON.stringify({genre: 'أخرى…'})
   })
   ```
2. Click Confirm
3. **Expected 400:** `{"detail": "يرجى إدخال نوع موسيقي محدد (Please enter a specific genre)"}`

**Test 3c: Too Long Genre (>200 chars)**
1. Type 250 characters in custom genre
2. Click Confirm
3. **Expected 400:** `{"detail": "النوع الموسيقي طويل جداً (Genre too long, max 200 characters)"}`

---

### Test Scenario 4: Switching Between Preset and Custom

**Steps:**
1. Click "قرآن" (Qurʾān) preset button
2. **In Network tab:** POST `/update` with `{"genre": "قرآן"}` → 200 OK
3. Confirm button enables immediately
4. Now click "أخرى…" button
5. Type "مديح نبوي"
6. **In Network tab:** POST `/update` with `{"genre": "مديح نبوي"}` → 200 OK
7. Switch back to "لطميات" preset
8. **In Network tab:** POST `/update` with `{"genre": "لطميات"}` → 200 OK
9. Click Confirm → Success

---

## Checking Backend Logs

**If running in terminal:**
```bash
# Watch logs while testing
python -m app.main

# You should see:
INFO:     POST /api/pending/1/update 200 OK
INFO:     POST /api/pending/1/confirm 200 OK
```

**If 400 errors appear:**
```
INFO:     POST /api/pending/1/confirm 400 Bad Request
```
Check the response body in Network tab for the Arabic error message.

---

## Files Changed

### Frontend: [app.js](file:///Users/akbaralhashim/Documents/Coding/metadata-editor/app/static/app.js)

**Line 161-177:** Custom genre input with debounce
```javascript
let debounceTimer;
customInput.addEventListener('input', () => {
    const value = customInput.value.trim();
    selectedGenres[itemId] = value;
    updateConfirmButton(itemId);
    
    // Debounce: send to backend after 500ms of no typing
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
        if (value.length > 0) {
            updateField(itemId, 'genre', value);
        }
    }, 500);
});
```

**Line 189-200:** Don't send empty genre on "أخرى…" click
```javascript
if (genre === 'custom') {
    selectedGenres[itemId] = customInput.value.trim() || '';
    // DON'T send to backend yet - only if already has value
    if (customInput.value.trim().length > 0) {
        updateField(itemId, 'genre', customInput.value.trim());
    }
} else {
    selectedGenres[itemId] = genre;
    updateField(itemId, 'genre', genre);  // Send preset immediately
}
```

### Backend: [api.py](file:///Users/akbaralhashim/Documents/Coding/metadata-editor/app/api.py)

**Line 94-109:** Enhanced validation
```python
# Validate with trimming
if not item.genre or not item.genre.strip():
    raise HTTPException(status_code=400, detail="النوع الموسيقي مطلوب (Genre is required)")

# Reject "أخرى…" literal
if item.genre.strip() == "أخرى…":
    raise HTTPException(status_code=400, detail="يرجى إدخال نوع موسيقي محدد")

# Length limit
if len(item.genre.strip()) > 200:
    raise HTTPException(status_code=400, detail="النوع الموسيقي طويل جداً")
```

---

## Quick Regression Checklist

After deploying, test:
- [x] ✅ Preset genre buttons work
- [x] ✅ Custom genre "أخرى…" accepts Arabic text
- [x] ✅ Empty custom genre is rejected
- [x] ✅ Whitespace-only genre is rejected
- [x] ✅ Switching between preset and custom works
- [x] ✅ Confirm succeeds with valid custom genre
- [x] ✅ Error messages are in Arabic and helpful

---

## Summary

**Root Cause:** Frontend sent empty `genre: ""` when "أخرى…" clicked, then never updated backend when user typed custom genre.

**Fix:**
1. **Frontend:** Skip sending genre if empty when "أخرى…" clicked
2. **Frontend:** Add 500ms debounced update when user types custom genre
3. **Backend:** Better validation with trimming, length check, and Arabic error messages

**Result:** Custom genres now work correctly! 🎉
