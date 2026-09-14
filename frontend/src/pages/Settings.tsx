import { useEffect, useState } from 'react';
import api from '../services/api';
import { Bell, ShieldCheck, Check } from 'lucide-react';

interface NotificationPreferences {
  verification_alerts: boolean;
  integrity_alerts: boolean;
  attribution_alerts: boolean;
  identity_alerts: boolean;
  metrics_updates: boolean;
  pipeline_updates: boolean;
  report_updates: boolean;
  email_notifications: boolean;
}

export default function Settings() {
  const [settings, setSettings] = useState<any>(null);
  const [preferences, setPreferences] = useState<NotificationPreferences>({
    verification_alerts: true,
    integrity_alerts: true,
    attribution_alerts: true,
    identity_alerts: true,
    metrics_updates: true,
    pipeline_updates: true,
    report_updates: true,
    email_notifications: false,
  });
  const [saveSuccess, setSaveSuccess] = useState(false);

  useEffect(() => {
    api.get('/api/v1/auth/settings').then(res => setSettings(res.data)).catch(() => {});
    api.get('/api/v1/notifications/preferences').then(res => {
      if (res.data) setPreferences(res.data);
    }).catch(() => {});
  }, []);

  const handleTogglePref = async (key: keyof NotificationPreferences) => {
    const updated = { ...preferences, [key]: !preferences[key] };
    setPreferences(updated);
    setSaveSuccess(false);

    try {
      await api.put('/api/v1/notifications/preferences', { [key]: updated[key] });
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 2000);
    } catch (err) {
      console.error('Failed to update notification preferences:', err);
    }
  };

  return (
    <div className="space-y-6 max-w-3xl mx-auto pb-12">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Settings</h1>
        <p className="text-sm text-gray-500 mt-0.5">
          Manage system configurations, data integrations, and notification alert preferences.
        </p>
      </div>

      {/* Notification Alert Preferences */}
      <div className="bg-white/90 backdrop-blur-md p-6 rounded-2xl border border-gray-200/80 shadow-sm">
        <div className="flex items-center justify-between border-b border-gray-100 pb-4 mb-5">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-50 text-blue-700 rounded-xl border border-blue-100">
              <Bell size={20} />
            </div>
            <div>
              <h3 className="font-bold text-gray-900 text-base">Research Monitoring & Alert Preferences</h3>
              <p className="text-xs text-gray-500 mt-0.5">Control which agent events trigger in-app alerts and monitoring tasks.</p>
            </div>
          </div>
          {saveSuccess && (
            <span className="flex items-center gap-1 text-xs font-semibold text-emerald-700 bg-emerald-50 px-2.5 py-1 rounded-lg border border-emerald-200">
              <Check size={14} /> Saved
            </span>
          )}
        </div>

        <div className="space-y-3.5">
          {[
            {
              key: 'verification_alerts' as const,
              label: 'Verification & Attestation Alerts',
              desc: 'Notifications when new publications require manual verification or confidence check.'
            },
            {
              key: 'integrity_alerts' as const,
              label: 'Research Integrity & Risk Warnings',
              desc: 'Alerts for missing DOIs, journal quartile flags, or metadata anomalies.'
            },
            {
              key: 'attribution_alerts' as const,
              label: 'Faculty Authorship & Attribution Events',
              desc: 'Updates when co-authorship linking or name disambiguation decisions are ready.'
            },
            {
              key: 'identity_alerts' as const,
              label: 'Scholarly Identity Disambiguation',
              desc: 'Alerts on Scopus ID, ORCID, or institutional affiliation updates.'
            },
            {
              key: 'metrics_updates' as const,
              label: 'Citation & Impact Metric Snapshots',
              desc: 'Notifications when h-index, i10-index, or citation totals update.'
            },
            {
              key: 'pipeline_updates' as const,
              label: 'Master Pipeline Synchronization Status',
              desc: 'Notifications when multi-agent discovery and synchronization cycles complete.'
            },
            {
              key: 'report_updates' as const,
              label: 'Accreditation & Institutional Report Generation',
              desc: 'Alerts when NAAC / NIRF research reports or evidence summaries are updated.'
            }
          ].map(item => (
            <div key={item.key} className="flex items-center justify-between p-3.5 rounded-xl bg-gray-50/70 border border-gray-100 hover:bg-gray-50 transition-colors">
              <div className="pr-4">
                <p className="text-sm font-semibold text-gray-800">{item.label}</p>
                <p className="text-xs text-gray-500 mt-0.5">{item.desc}</p>
              </div>
              <button
                type="button"
                onClick={() => handleTogglePref(item.key)}
                className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none ${
                  preferences[item.key] ? 'bg-blue-600' : 'bg-gray-300'
                }`}
              >
                <span
                  className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                    preferences[item.key] ? 'translate-x-5' : 'translate-x-0'
                  }`}
                />
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* External Research Sources */}
      <div className="bg-white/90 backdrop-blur-md p-6 rounded-2xl border border-gray-200/80 shadow-sm">
        <div className="flex items-center gap-3 border-b border-gray-100 pb-4 mb-4">
          <div className="p-2 bg-emerald-50 text-emerald-700 rounded-xl border border-emerald-100">
            <ShieldCheck size={20} />
          </div>
          <div>
            <h3 className="font-bold text-gray-900 text-base">Research Source Configuration</h3>
            <p className="text-xs text-gray-500 mt-0.5">External bibliographic APIs configured securely on the server.</p>
          </div>
        </div>
        
        <div className="space-y-2.5">
          {['OpenAlex', 'Crossref', 'Scopus', 'Web of Science'].map(source => {
            const isConfigured = settings?.api_keys_configured?.includes(source.toLowerCase()) || source === 'OpenAlex' || source === 'Crossref';
            return (
              <div key={source} className="flex justify-between items-center bg-gray-50/70 border border-gray-100 p-3.5 rounded-xl">
                <span className="text-sm font-semibold text-gray-800">{source}</span>
                {isConfigured ? (
                  <span className="inline-flex items-center gap-1 text-emerald-700 text-xs font-semibold px-2.5 py-1 bg-emerald-50 border border-emerald-200 rounded-full">
                    <Check size={12} /> Active & Configured
                  </span>
                ) : (
                  <span className="text-gray-500 text-xs font-medium px-2.5 py-1 bg-gray-100 rounded-full">
                    Optional / Inactive
                  </span>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
