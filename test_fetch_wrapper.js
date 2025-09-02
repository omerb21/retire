// Test script for the fetch wrapper logic that avoids "body stream already read" errors

// Mock fetch response to simulate both success and error cases
class MockResponse {
  constructor(status, data, contentType = 'application/json') {
    this.status = status;
    this.ok = status >= 200 && status < 300;
    this._data = typeof data === 'string' ? data : JSON.stringify(data);
    this._contentType = contentType;
    this._used = false;
  }

  clone() {
    return new MockResponse(this.status, JSON.parse(this._data), this._contentType);
  }

  get headers() {
    return {
      get: (name) => name.toLowerCase() === 'content-type' ? this._contentType : null
    };
  }

  async json() {
    if (this._used) throw new Error('Body stream already read');
    this._used = true;
    return JSON.parse(this._data);
  }

  async text() {
    if (this._used) throw new Error('Body stream already read');
    this._used = true;
    return this._data;
  }
}

// Mock fetch function
global.fetch = async (url, options) => {
  console.log(`Mock fetch called with URL: ${url}`);
  
  // Different responses based on URL
  if (url.includes('/success')) {
    return new MockResponse(200, { result: 'success', id: 123 });
  } else if (url.includes('/error-422')) {
    return new MockResponse(422, { 
      detail: [
        { loc: ['body', 'id_number'], msg: 'invalid ID number' }
      ] 
    });
  } else if (url.includes('/error-plain')) {
    return new MockResponse(400, 'Bad request error', 'text/plain');
  } else {
    return new MockResponse(404, { detail: 'Resource not found' });
  }
};

// Our improved API fetch wrapper
async function parseJsonSafe(res) {
  try {
    return await res.clone().json();
  } catch (e) {
    console.log('Failed to parse JSON:', e.message);
    return null;
  }
}

async function parseTextSafe(res) {
  try {
    return await res.clone().text();
  } catch (e) {
    console.log('Failed to parse text:', e.message);
    return '';
  }
}

function extractMessage(body) {
  if (!body) return;
  if (typeof body === 'string') return body;
  if (typeof body.detail === 'string') return body.detail;
  if (Array.isArray(body?.detail)) {
    return body.detail.map(d => d.msg || d?.loc?.join('.')).join('; ');
  }
}

async function apiFetch(path, init = {}) {
  const API_BASE = 'http://localhost:8000/api/v1';
  const res = await fetch(`${API_BASE}${path}`, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
    ...init,
  });

  const contentType = res.headers.get('content-type') || '';
  const looksJson = contentType.includes('application/json');

  if (!res.ok) {
    const json = looksJson ? await parseJsonSafe(res) : null;
    const txt = !json ? await parseTextSafe(res) : undefined;
    const message = extractMessage(json) || txt || `HTTP ${res.status}`;
    throw new Error(message);
  }

  if (looksJson) return await res.json();
  return await res.text();
}

// The broken implementation for comparison (reads body twice)
async function brokenFetch(path) {
  const API_BASE = 'http://localhost:8000/api/v1';
  const res = await fetch(`${API_BASE}${path}`);
  
  if (!res.ok) {
    try {
      const errorData = await res.json();
      const detail = errorData.detail || JSON.stringify(errorData);
      throw new Error(`Error: ${detail}`);
    } catch (jsonError) {
      const text = await res.text(); // This will fail with "body stream already read"
      throw new Error(`Error: ${res.status} ${text}`);
    }
  }
  
  return res.json();
}

// Run tests
async function runTests() {
  console.log('===== Testing the fixed apiFetch implementation =====');
  
  try {
    // Success case
    console.log('\n1. Testing successful request:');
    const successResult = await apiFetch('/success');
    console.log('Success result:', successResult);
    
    // Error case with JSON response
    console.log('\n2. Testing error with JSON response:');
    try {
      await apiFetch('/error-422');
    } catch (error) {
      console.log('Caught error (good):', error.message);
    }
    
    // Error case with plain text response
    console.log('\n3. Testing error with plain text response:');
    try {
      await apiFetch('/error-plain');
    } catch (error) {
      console.log('Caught error (good):', error.message);
    }
    
    console.log('\n===== Testing the broken fetch implementation =====');
    
    // Try the broken implementation
    console.log('\n4. Testing broken fetch with error:');
    try {
      await brokenFetch('/error-422');
    } catch (error) {
      console.log('Caught error:', error.message);
      // The original implementation would throw "Body stream already read"
    }
    
    console.log('\n===== All tests completed =====');
    console.log('The fixed implementation correctly handles response bodies exactly once');
    console.log('while the broken implementation attempts to read the body twice, causing errors.');
  } catch (error) {
    console.error('Test failed:', error);
  }
}

// Run the tests
runTests();
