import { useState } from 'react';
import api from './api';

const Login = ({ onLogin }) => {
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleLogin = async (e) => {
    e.preventDefault();
    if (!password) {
      setError("❌ Password required");
      return;
    }

    setLoading(true);
    setError('');
    try {
      const res = await api.post('/login', { password });
      if (res.data.success) {
        localStorage.setItem('kingin_jwt', res.data.token);
        onLogin(res.data.token);
      } else {
        setError(res.data.error || "Invalid Access Token");
      }
    } catch (err) {
      setError('Connection failed. Is the backend running?');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={styles.container}>
      <div style={styles.card}>
        <div style={styles.logoCircle}>KI</div>
        <h1 style={styles.title}>KINGIN</h1>
        <p style={styles.subtitle}>INSTITUTIONAL CONTROL ROOM</p>
        
        <form onSubmit={handleLogin} style={styles.form}>
          <div style={styles.inputGroup}>
            <label style={styles.label}>ACCESS PASSWORD</label>
            <input 
              type="password" 
              style={styles.input}
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>
          
          {error && <div style={styles.error}>{error}</div>}
          
          <button style={styles.button} disabled={loading}>
            {loading ? 'AUTHENTICATING...' : 'SECURE ACCESS'}
          </button>
        </form>
        
        <div style={styles.footer}>
          System Hardened • JWT Secured • Local Bridge
        </div>
      </div>
    </div>
  );
};

const styles = {
  container: {
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    height: '100vh', background: '#080B12', color: '#fff', fontFamily: 'Inter, sans-serif'
  },
  card: {
    width: '380px', padding: '50px 40px', background: '#0F1420', 
    border: '1px solid #1C2333', borderRadius: '16px', textAlign: 'center',
    boxShadow: '0 20px 50px rgba(0,0,0,0.5)'
  },
  logoCircle: {
    width: '60px', height: '60px', borderRadius: '50%', background: '#FFD700',
    color: '#000', display: 'flex', alignItems: 'center', justifyContent: 'center',
    margin: '0 auto 20px', fontWeight: 800, fontSize: '20px'
  },
  title: { fontSize: '28px', fontWeight: 800, letterSpacing: '4px', margin: 0, color: '#FFD700' },
  subtitle: { fontSize: '10px', color: '#6B7280', letterSpacing: '2px', marginBottom: '40px', fontWeight: 600 },
  form: { textAlign: 'left' },
  inputGroup: { marginBottom: '24px' },
  label: { display: 'block', fontSize: '10px', fontWeight: 700, color: '#9CA3AF', marginBottom: '8px', letterSpacing: '1px' },
  input: {
    width: '100%', padding: '14px', background: '#080B12', border: '1px solid #1C2333',
    borderRadius: '8px', color: '#fff', outline: 'none', transition: 'border-color 0.2s'
  },
  error: { color: '#FF3B5C', fontSize: '12px', marginBottom: '20px', textAlign: 'center' },
  button: {
    width: '100%', padding: '16px', background: '#FFD700', border: 'none',
    borderRadius: '8px', color: '#000', fontWeight: 700, cursor: 'pointer',
    letterSpacing: '1px', transition: 'transform 0.1s'
  },
  footer: { marginTop: '40px', fontSize: '10px', color: '#374151', textTransform: 'uppercase', letterSpacing: '1px' }
};

export default Login;