import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { AuthLayout } from '../../components/auth/AuthLayout';
import { OtpInput } from '../../components/auth/OtpInput';
import { StepProgress } from '../../components/ui/StepProgress';
import { authService } from '../../services/api';
import type { IdentifierType, ForgotStep } from '../../types';

const STEPS = [
  { label: 'Identify' },
  { label: 'Verify' },
  { label: 'Reset' },
];

const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const phoneRegex = /^[6-9]\d{9}$/;

export const ForgotPasswordPage: React.FC = () => {
  const navigate = useNavigate();
  const [step, setStep] = useState<ForgotStep>('identifier');
  const [identifierType, setIdentifierType] = useState<IdentifierType>('email');
  const [identifier, setIdentifier] = useState('');
  const [otp, setOtp] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPwd, setShowPwd] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [countdown, setCountdown] = useState(60);
  const [timerActive, setTimerActive] = useState(false);
  const [verificationToken, setVerificationToken] = useState<string | null>(null);

  const stepIndex = step === 'identifier' ? 0 : step === 'otp' ? 1 : step === 'new_password' ? 2 : 3;

  React.useEffect(() => {
    if (!timerActive) return;
    const interval = setInterval(() => {
      setCountdown(c => {
        if (c <= 1) { clearInterval(interval); setTimerActive(false); return 0; }
        return c - 1;
      });
    }, 1000);
    return () => clearInterval(interval);
  }, [timerActive]);

  const startTimer = () => { setCountdown(60); setTimerActive(true); };

  const inputBase = () =>
    'w-full bg-[#0F0F0F] border border-[#2A2A2A] rounded-[10px] px-4 py-3 text-white placeholder-[#3A3A3A] outline-none transition-all font-medium text-sm focus:border-[#E8571A] focus:ring-[3px] focus:ring-[#E8571A]/20';

  const handleSendOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    const clean = identifier.replace(/\s/g, '');
    if (identifierType === 'email' && !emailRegex.test(clean)) return setError('Enter a valid email address');
    if (identifierType === 'phone' && !phoneRegex.test(clean)) return setError('Enter a valid 10-digit phone number');
    setIsLoading(true);
    try {
      await authService.sendOtp({
        identifier: clean,
        identifier_type: identifierType,
        purpose: 'forgot_password'
      });
      startTimer();
      setStep('otp');
    } catch (err: any) {
      if (!err.response) {
        setError('Cannot connect to backend server. Is it running?');
      } else if (err.response?.data?.errors?.identifier) {
        const idErr = err.response.data.errors.identifier;
        setError(Array.isArray(idErr) ? idErr[0] : idErr);
      } else if (err.response?.data?.message) {
        setError(err.response.data.message);
      } else {
        setError('Failed to send OTP. Please try again.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleVerifyOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (otp.length < 6) return setError('Please enter the complete 6-digit OTP');
    setIsLoading(true);
    try {
      const res = await authService.verifyOtp({
        identifier: identifier.replace(/\s/g, ''),
        identifier_type: identifierType,
        otp,
        purpose: 'forgot_password'
      });
      setVerificationToken(res.data.verification_token);
      setStep('new_password');
    } catch (err: any) {
      setError(err.response?.data?.errors?.otp || 'Invalid or expired OTP.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleResetPassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (newPassword.length < 8) return setError('Password must be at least 8 characters');
    if (newPassword !== confirmPassword) return setError('Passwords do not match');
    setIsLoading(true);
    try {
      await authService.resetPassword({
        identifier: identifier.replace(/\s/g, ''),
        identifier_type: identifierType,
        verification_token: verificationToken,
        new_password: newPassword
      });
      setStep('success');
    } catch (err: any) {
      setError(err.response?.data?.message || 'Failed to reset password. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const ErrorBanner = () => error ? (
    <div className="mb-4 bg-red-500/10 border border-red-500/20 text-red-400 text-sm rounded-lg p-3 flex gap-2 items-start">
      <svg className="w-4 h-4 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
          d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
      </svg>
      {error}
    </div>
  ) : null;

  const SpinBtn = ({ label, loading }: { label: string; loading?: boolean }) => (
    <button type="submit" disabled={loading}
      className="w-full bg-[#E8571A] hover:bg-[#FF6B35] text-white font-semibold py-3 rounded-[10px] transition-all orange-glow disabled:opacity-60 flex items-center justify-center gap-2">
      {loading ? (
        <><svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg> Processing...</>
      ) : label}
    </button>
  );

  return (
    <AuthLayout heroTitle={'Reset your\npassword securely'}>
      <div className="bg-[#1A1A1A] rounded-2xl border border-[#2A2A2A] p-8 shadow-2xl relative overflow-hidden glass-card">
        <div className="absolute -top-32 -right-32 w-64 h-64 bg-[#E8571A]/5 rounded-full blur-[80px] pointer-events-none" />

        {step !== 'success' && (
          <StepProgress steps={STEPS} currentStep={stepIndex} className="mb-8 relative z-10" />
        )}

        {/* ── STEP 1 ── */}
        {step === 'identifier' && (
          <>
            <div className="mb-6 relative z-10">
              <h2 className="text-2xl font-bold text-white">Forgot password?</h2>
              <p className="text-[#9A9690] mt-1 text-sm">Enter your registered email or phone</p>
            </div>
            <ErrorBanner />
            <form onSubmit={handleSendOtp} className="space-y-4 relative z-10">
              <div className="flex bg-[#0F0F0F] rounded-[10px] p-1 border border-[#2A2A2A]">
                {(['email', 'phone'] as IdentifierType[]).map(t => (
                  <button key={t} type="button"
                    onClick={() => { setIdentifierType(t); setIdentifier(''); setError(null); }}
                    className={`flex-1 py-1.5 text-xs font-semibold rounded-[8px] transition-all ${
                      identifierType === t ? 'bg-[#E8571A] text-white' : 'text-[#9A9690] hover:text-white'
                    }`}>
                    {t === 'email' ? '✉ Email' : '📱 Phone'}
                  </button>
                ))}
              </div>
              <div>
                <label className="block text-[12px] font-semibold text-[#9A9690] mb-1.5">
                  {identifierType === 'email' ? 'Email address' : 'Phone number'}
                </label>
                <input type={identifierType === 'email' ? 'email' : 'tel'} value={identifier}
                  onChange={e => setIdentifier(e.target.value)} className={inputBase()}
                  placeholder={identifierType === 'email' ? 'owner@example.com' : '9876543210'} autoFocus />
              </div>
              <SpinBtn label="Send OTP →" loading={isLoading} />
            </form>
            <div className="mt-6 text-center text-[13px] text-[#9A9690] relative z-10">
              <Link to="/login" className="text-[#E8571A] hover:text-[#FF6B35] font-semibold">← Back to Login</Link>
            </div>
          </>
        )}

        {/* ── STEP 2 ── */}
        {step === 'otp' && (
          <>
            <div className="mb-6 relative z-10 text-center">
              <h2 className="text-2xl font-bold text-white">Enter OTP</h2>
              <p className="text-[#9A9690] mt-1 text-sm">
                Code sent to <span className="text-white font-semibold">{identifier}</span>
              </p>
            </div>
            <ErrorBanner />
            <form onSubmit={handleVerifyOtp} className="space-y-6 relative z-10">
              <OtpInput value={otp} onChange={setOtp} error={!!error} disabled={isLoading} />
              <div className="text-center">
                {timerActive ? (
                  <p className="text-[#9A9690] text-sm">Resend in <span className="text-[#E8571A] font-bold tabular-nums">{countdown}s</span></p>
                ) : (
                  <button type="button" onClick={async () => {
                    setOtp(''); setError(null); setIsLoading(true);
                    try {
                      await authService.sendOtp({
                        identifier: identifier.replace(/\s/g, ''),
                        identifier_type: identifierType,
                        purpose: 'forgot_password'
                      });
                      startTimer();
                    } catch (err: any) {
                      setError('Failed to resend OTP.');
                    } finally {
                      setIsLoading(false);
                    }
                  }} className="text-[#E8571A] hover:text-[#FF6B35] text-sm font-semibold">Resend OTP</button>
                )}
              </div>
              <div className="flex gap-3">
                <button type="button" onClick={() => { setStep('identifier'); setError(null); setOtp(''); }}
                  className="flex-1 py-3 border border-[#2A2A2A] text-[#9A9690] hover:text-white rounded-[10px] font-medium text-sm transition-all">← Back</button>
                <button type="submit" disabled={isLoading || otp.length < 6}
                  className="flex-1 bg-[#E8571A] hover:bg-[#FF6B35] text-white font-semibold py-3 rounded-[10px] transition-all orange-glow disabled:opacity-60 flex items-center justify-center gap-2">
                  {isLoading ? <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" /></svg> : 'Verify'}
                </button>
              </div>
            </form>
          </>
        )}

        {/* ── STEP 3 ── */}
        {step === 'new_password' && (
          <>
            <div className="mb-6 relative z-10">
              <h2 className="text-2xl font-bold text-white">New password</h2>
              <p className="text-[#9A9690] mt-1 text-sm">Choose a strong new password</p>
            </div>
            <ErrorBanner />
            <form onSubmit={handleResetPassword} className="space-y-4 relative z-10">
              <div>
                <label className="block text-[12px] font-semibold text-[#9A9690] mb-1.5">New password</label>
                <div className="relative">
                  <input type={showPwd ? 'text' : 'password'} value={newPassword}
                    onChange={e => setNewPassword(e.target.value)} className={`${inputBase()} pr-11`}
                    placeholder="Min. 8 characters" autoFocus />
                  <button type="button" tabIndex={-1} onClick={() => setShowPwd(p => !p)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-[#4A4A4A] hover:text-[#9A9690] p-1">
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={showPwd ? "M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" : "M15 12a3 3 0 11-6 0 3 3 0 016 0zM2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"} />
                    </svg>
                  </button>
                </div>
              </div>
              <div>
                <label className="block text-[12px] font-semibold text-[#9A9690] mb-1.5">Confirm password</label>
                <div className="relative">
                  <input type={showConfirm ? 'text' : 'password'} value={confirmPassword}
                    onChange={e => setConfirmPassword(e.target.value)} className={`${inputBase()} pr-11`}
                    placeholder="Re-enter password" />
                  <button type="button" tabIndex={-1} onClick={() => setShowConfirm(p => !p)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-[#4A4A4A] hover:text-[#9A9690] p-1">
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={showConfirm ? "M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" : "M15 12a3 3 0 11-6 0 3 3 0 016 0zM2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"} />
                    </svg>
                  </button>
                </div>
              </div>
              <SpinBtn label="Reset Password" loading={isLoading} />
            </form>
          </>
        )}

        {/* ── SUCCESS ── */}
        {step === 'success' && (
          <div className="text-center py-8 relative z-10">
            <div className="w-20 h-20 bg-green-500/10 rounded-full flex items-center justify-center mx-auto mb-6">
              <svg className="w-10 h-10 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <h2 className="text-2xl font-bold text-white mb-2">Password reset!</h2>
            <p className="text-[#9A9690] text-sm mb-8">Your password has been updated successfully.</p>
            <button onClick={() => navigate('/login')}
              className="bg-[#E8571A] hover:bg-[#FF6B35] text-white font-semibold px-8 py-3 rounded-[10px] transition-all orange-glow">
              Sign In Now
            </button>
          </div>
        )}
      </div>
    </AuthLayout>
  );
};
