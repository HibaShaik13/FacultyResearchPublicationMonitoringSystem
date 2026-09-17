import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import api from '../services/api';
import {
  Search,
  ShieldCheck,
  BarChart3,
  Lightbulb,
  Mail,
  Lock,
  Eye,
  EyeOff,
  ArrowRight,
  Landmark,
} from 'lucide-react';

export default function Login() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(true);
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      const params = new URLSearchParams();
      params.append('username', email.trim());
      params.append('password', password);

      const res = await api.post('/api/v1/auth/login', params);
      await login(res.data.access_token);
      navigate('/');
    } catch (err: any) {
      if (err.response?.data?.detail) {
        setError(err.response.data.detail);
      } else if (!err.response) {
        setError('Unable to reach research authentication server. Please verify backend status and network connection.');
      } else {
        setError('Invalid email or password. Please check your credentials.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen w-full relative flex items-center justify-between overflow-hidden bg-slate-900 font-sans selection:bg-blue-500 selection:text-white">
      {/* 1. Full Vignan University Campus Background Image */}
      <div
        className="absolute inset-0 bg-cover bg-center bg-no-repeat transition-all duration-700"
        style={{
          backgroundImage: `url('/vignan_building_sign.jpg'), url('/vignan_campus_bg.jpg'), url('/campus_bg.jpg')`,
        }}
      />

      {/* Subtle, soft natural gradient to enhance contrast for text without darkening the campus */}
      <div className="absolute inset-0 bg-gradient-to-r from-blue-900/35 via-transparent to-blue-950/20 pointer-events-none" />
      <div className="absolute inset-0 bg-gradient-to-t from-black/25 via-transparent to-black/15 pointer-events-none" />

      {/* Top Left: Official Vignan University Logo Header */}
      <div className="absolute top-6 left-8 sm:left-12 z-20 flex items-center">
        <div className="bg-white/95 backdrop-blur-md px-4 py-2 rounded-2xl shadow-xl border border-white/80 flex items-center gap-3">
          <img
            src="/vignan_official_logo.png"
            alt="Vignan University Logo"
            className="h-10 sm:h-12 w-auto object-contain"
            onError={(e) => {
              e.currentTarget.style.display = 'none';
            }}
          />
          <div className="flex flex-col">
            <div className="flex items-center gap-1.5">
              <span className="text-xl sm:text-2xl font-black text-red-600 tracking-tight leading-none">
                VIGNAN'S
              </span>
            </div>
            <span className="text-[9px] font-bold text-slate-700 uppercase tracking-wider mt-0.5">
              Foundation for Science, Technology & Research
            </span>
            <div className="mt-0.5 inline-block bg-blue-600 text-white text-[8px] font-semibold px-2 py-0.5 rounded-full w-fit">
              (Deemed to be University) - Estd. u/s 3 of UGC Act 1956
            </div>
          </div>
        </div>
      </div>

      {/* Top Right: Tagline Script Typography */}
      <div className="absolute top-8 right-8 sm:right-14 z-20 text-right hidden md:block">
        <div className="font-serif italic text-white/95 text-lg sm:text-xl font-medium tracking-wide drop-shadow-[0_2px_4px_rgba(0,0,0,0.6)] leading-snug">
          <div>Innovate</div>
          <div>Integrate</div>
          <div>Impact</div>
        </div>
      </div>

      {/* Left Side: Hero Title, Subtitle, and 4 Action Circular Badges */}
      <div className="relative z-10 w-full lg:w-3/5 px-8 sm:px-12 lg:px-20 py-24 flex flex-col justify-between min-h-screen">
        <div className="my-auto pt-20 max-w-xl">
          {/* Main Hero Heading */}
          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-extrabold text-white leading-[1.12] tracking-tight drop-shadow-[0_2px_8px_rgba(0,0,0,0.5)]">
            Research for a <br />
            <span className="text-sky-300 drop-shadow-[0_2px_10px_rgba(14,165,233,0.4)]">
              Better Tomorrow
            </span>
          </h1>

          {/* Subheading */}
          <p className="text-base sm:text-lg text-white/95 mt-5 font-normal leading-relaxed drop-shadow-[0_1px_4px_rgba(0,0,0,0.6)] max-w-lg">
            Turning Faculty Research into Verified Intelligence and Real-World Impact.
          </p>

          {/* 4 Feature Circular Badges */}
          <div className="flex items-center gap-6 sm:gap-8 mt-10">
            <div className="flex flex-col items-center gap-2 group cursor-default">
              <div className="w-13 h-13 sm:w-14 sm:h-14 rounded-full border border-white/50 bg-white/20 backdrop-blur-md flex items-center justify-center text-white shadow-lg group-hover:bg-white/30 group-hover:scale-105 transition-all">
                <Search size={22} className="text-white" />
              </div>
              <span className="text-xs font-semibold text-white drop-shadow-[0_1px_3px_rgba(0,0,0,0.8)] tracking-wide">
                Discover
              </span>
            </div>

            <div className="flex flex-col items-center gap-2 group cursor-default">
              <div className="w-13 h-13 sm:w-14 sm:h-14 rounded-full border border-white/50 bg-white/20 backdrop-blur-md flex items-center justify-center text-white shadow-lg group-hover:bg-white/30 group-hover:scale-105 transition-all">
                <ShieldCheck size={22} className="text-white" />
              </div>
              <span className="text-xs font-semibold text-white drop-shadow-[0_1px_3px_rgba(0,0,0,0.8)] tracking-wide">
                Verify
              </span>
            </div>

            <div className="flex flex-col items-center gap-2 group cursor-default">
              <div className="w-13 h-13 sm:w-14 sm:h-14 rounded-full border border-white/50 bg-white/20 backdrop-blur-md flex items-center justify-center text-white shadow-lg group-hover:bg-white/30 group-hover:scale-105 transition-all">
                <BarChart3 size={22} className="text-white" />
              </div>
              <span className="text-xs font-semibold text-white drop-shadow-[0_1px_3px_rgba(0,0,0,0.8)] tracking-wide">
                Analyze
              </span>
            </div>

            <div className="flex flex-col items-center gap-2 group cursor-default">
              <div className="w-13 h-13 sm:w-14 sm:h-14 rounded-full border border-white/50 bg-white/20 backdrop-blur-md flex items-center justify-center text-white shadow-lg group-hover:bg-white/30 group-hover:scale-105 transition-all">
                <Lightbulb size={22} className="text-white" />
              </div>
              <span className="text-xs font-semibold text-white drop-shadow-[0_1px_3px_rgba(0,0,0,0.8)] tracking-wide">
                Advance
              </span>
            </div>
          </div>
        </div>

        {/* Bottom Left: Quotation */}
        <div className="pt-8">
          <p className="font-serif italic text-white/95 text-base sm:text-lg drop-shadow-[0_1px_4px_rgba(0,0,0,0.7)]">
            “Knowledge grows when it is shared.”
          </p>
          <div className="w-20 h-0.5 bg-white/70 rounded-full mt-1.5 shadow" />
        </div>
      </div>

      {/* Right Side: Floating Frosted Login Card */}
      <div className="relative z-10 w-full lg:w-2/5 px-6 sm:px-10 lg:px-12 py-16 flex items-center justify-center">
        <div className="w-full max-w-md bg-white/95 backdrop-blur-2xl rounded-[2.5rem] p-8 sm:p-10 shadow-[0_25px_60px_rgba(0,0,0,0.35)] border border-white/90 space-y-6">
          {/* Card Header */}
          <div>
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Welcome to
            </p>
            <h2 className="text-2xl sm:text-3xl font-black text-slate-900 tracking-tight mt-0.5">
              VIGNAN'S
            </h2>
            <div className="flex items-center gap-2 mt-1">
              <span className="w-2 h-2 rounded-full bg-blue-600 inline-block" />
              <h3 className="text-sm sm:text-base font-bold text-blue-700">
                Research Intelligence Platform
              </h3>
            </div>
            <p className="text-xs text-slate-500 mt-2">
              Sign in to access your research workspace
            </p>
          </div>

          {/* Login Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div className="p-3 text-xs text-rose-700 bg-rose-50 border border-rose-200 rounded-xl font-medium animate-in fade-in">
                {error}
              </div>
            )}

            {/* Email Input */}
            <div className="space-y-1.5">
              <label className="text-xs font-bold text-slate-700 uppercase tracking-wider flex items-center gap-1.5">
                <Mail size={13} className="text-blue-600" /> Institutional Email
              </label>
              <div className="relative">
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="name@vignan.ac.in"
                  required
                  className="w-full pl-4 pr-4 py-3 bg-slate-50/90 border border-slate-200 rounded-xl text-xs sm:text-sm text-slate-900 font-medium placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-600 focus:bg-white transition-all shadow-inner"
                />
              </div>
            </div>

            {/* Password Input */}
            <div className="space-y-1.5">
              <label className="text-xs font-bold text-slate-700 uppercase tracking-wider flex items-center gap-1.5">
                <Lock size={13} className="text-blue-600" /> Password
              </label>
              <div className="relative">
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  required
                  className="w-full pl-4 pr-10 py-3 bg-slate-50/90 border border-slate-200 rounded-xl text-xs sm:text-sm text-slate-900 font-medium placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-600 focus:bg-white transition-all shadow-inner"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 focus:outline-none"
                >
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            {/* Remember me & Forgot Password */}
            <div className="flex items-center justify-between text-xs pt-1">
              <label className="flex items-center gap-2 cursor-pointer text-slate-600 font-medium">
                <input
                  type="checkbox"
                  checked={rememberMe}
                  onChange={(e) => setRememberMe(e.target.checked)}
                  className="w-3.5 h-3.5 rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                />
                <span>Remember me</span>
              </label>
              <a
                href="#forgot"
                onClick={(e) => {
                  e.preventDefault();
                  alert('Please contact VFSTR IT Helpdesk (helpdesk@vignan.ac.in) for password reset assistance.');
                }}
                className="text-blue-600 hover:text-blue-800 font-semibold"
              >
                Forgot password?
              </a>
            </div>

            {/* Primary Sign In Button */}
            <button
              type="submit"
              disabled={isLoading}
              className="w-full py-3.5 px-4 bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-700 hover:to-blue-800 text-white font-bold text-sm rounded-xl shadow-lg shadow-blue-600/30 flex items-center justify-center gap-2 transition-all duration-200 disabled:opacity-50"
            >
              {isLoading ? (
                <span>Signing in...</span>
              ) : (
                <>
                  <span>Sign In</span>
                  <ArrowRight size={16} />
                </>
              )}
            </button>

            {/* Quick Demo Credentials */}
            <div className="pt-1">
              <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider text-center mb-1.5">
                Quick Test Accounts (Click to autofill)
              </p>
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => {
                    setEmail('hodcse@vignan.ac.in');
                    setPassword('faculty123');
                  }}
                  className="px-2.5 py-1.5 bg-blue-50 hover:bg-blue-100/80 text-blue-700 border border-blue-200/80 rounded-lg text-[11px] font-semibold text-center transition-all shadow-xs flex flex-col items-center"
                >
                  <span className="font-bold">Dr. Venkatrama</span>
                  <span className="text-[9px] text-blue-500 font-normal">Faculty (CSE)</span>
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setEmail('admin@vignan.ac.in');
                    setPassword('admin');
                  }}
                  className="px-2.5 py-1.5 bg-slate-100 hover:bg-slate-200/80 text-slate-700 border border-slate-200 rounded-lg text-[11px] font-semibold text-center transition-all shadow-xs flex flex-col items-center"
                >
                  <span className="font-bold">System Admin</span>
                  <span className="text-[9px] text-slate-500 font-normal">Research Admin</span>
                </button>
              </div>
            </div>

            {/* Divider */}
            <div className="relative flex items-center py-2">
              <div className="flex-grow border-t border-slate-200" />
              <span className="flex-shrink-0 mx-3 text-slate-400 text-[11px] font-bold uppercase tracking-wider">
                OR
              </span>
              <div className="flex-grow border-t border-slate-200" />
            </div>

            {/* Institutional SSO Button */}
            <button
              type="button"
              onClick={() => {
                alert('Institutional SSO redirected to Vignan Single Sign-On portal.');
              }}
              className="w-full py-3 px-4 bg-slate-50 hover:bg-slate-100 text-slate-700 border border-slate-200 font-semibold text-xs rounded-xl shadow-sm flex items-center justify-center gap-2 transition-all"
            >
              <Landmark size={15} className="text-blue-600" />
              <span>Sign in with Institutional SSO</span>
            </button>
          </form>

          {/* Card Footer Micro-Nav */}
          <div className="pt-2 border-t border-slate-100 text-center text-[11px] font-medium text-slate-400 flex items-center justify-center gap-2">
            <span>Discover</span>
            <span>•</span>
            <span>Verify</span>
            <span>•</span>
            <span>Analyze</span>
            <span>•</span>
            <span>Advance</span>
          </div>
        </div>
      </div>

      {/* Bottom Right: Slogan */}
      <div className="absolute bottom-6 right-8 z-20 text-right hidden sm:block">
        <div className="font-serif italic text-white/95 text-xs sm:text-sm drop-shadow-[0_1px_3px_rgba(0,0,0,0.8)] leading-tight">
          <div>Empowering Minds</div>
          <div>for a Brighter Tomorrow</div>
        </div>
      </div>
    </div>
  );
}
