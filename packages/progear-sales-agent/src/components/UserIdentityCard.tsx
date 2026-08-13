'use client';

import { User, Shield, Users, Mail } from 'lucide-react';

interface UserInfo {
  email?: string;
  name?: string;
  sub?: string;
  groups?: string[];
}

interface Props {
  user: UserInfo | null;
}

// Map groups to their display info
const groupInfo: Record<string, { name: string; color: string; access: string[] }> = {
  'ProGear-Sales': {
    name: 'Sales',
    color: '#3b82f6',
    access: ['Sales', 'Inventory (read)', 'Customer', 'Pricing (read)']
  },
  'ProGear-Warehouse': {
    name: 'Warehouse',
    color: '#10b981',
    access: ['Inventory']
  },
  'ProGear-Finance': {
    name: 'Finance',
    color: '#f59e0b',
    access: ['Pricing']
  },
};

export default function UserIdentityCard({ user }: Props) {
  if (!user || !user.email || user.email === 'anonymous') {
    return (
      <div className="bg-white rounded-xl border-2 border-neutral-border shadow-sm overflow-hidden">
        <div className="bg-gradient-to-r from-gray-600 to-gray-500 px-4 py-3 border-b border-neutral-border">
          <h3 className="text-white font-semibold flex items-center gap-2">
            <User className="w-5 h-5" />
            User Identity
          </h3>
        </div>
        <div className="p-4 text-center">
          <div className="w-12 h-12 bg-gray-200 rounded-full mx-auto mb-3 flex items-center justify-center">
            <User className="w-6 h-6 text-gray-400" />
          </div>
          <p className="text-gray-500 text-sm">Sign in to see your identity</p>
        </div>
      </div>
    );
  }

  const userGroups = user.groups || [];
  const matchedGroups = userGroups.filter(g => groupInfo[g]);

  return (
    <div className="bg-white rounded-xl border-2 border-neutral-border shadow-sm overflow-hidden">
      <div className="bg-gradient-to-r from-tech-purple to-tech-purple-light px-4 py-3 border-b border-neutral-border">
        <h3 className="text-white font-semibold flex items-center gap-2">
          <User className="w-5 h-5" />
          User Identity
        </h3>
      </div>

      <div className="p-4">
        {/* User Info */}
        <div className="flex items-center gap-3 mb-4 pb-4 border-b border-gray-100">
          <div className="w-12 h-12 bg-gradient-to-br from-tech-purple to-accent rounded-full flex items-center justify-center text-white font-bold text-lg">
            {(user.name || user.email || 'U').charAt(0).toUpperCase()}
          </div>
          <div className="flex-1 min-w-0">
            <div className="font-semibold text-gray-800 truncate">
              {user.name || user.email?.split('@')[0]}
            </div>
            <div className="text-sm text-gray-500 truncate flex items-center gap-1">
              <Mail className="w-3 h-3" />
              {user.email}
            </div>
          </div>
        </div>

        {/* Groups */}
        <div className="mb-4">
          <div className="text-xs text-gray-500 uppercase font-semibold mb-2 flex items-center gap-1">
            <Users className="w-3 h-3" />
            Groups
          </div>
          <div className="space-y-2">
            {matchedGroups.length > 0 ? (
              matchedGroups.map((group) => {
                const info = groupInfo[group];
                return (
                  <div
                    key={group}
                    className="flex items-center gap-2 p-2 rounded-lg"
                    style={{ backgroundColor: `${info.color}15` }}
                  >
                    <div
                      className="w-6 h-6 rounded flex items-center justify-center text-white text-xs font-bold"
                      style={{ backgroundColor: info.color }}
                    >
                      {info.name.charAt(0)}
                    </div>
                    <span className="text-sm font-medium text-gray-700">{group}</span>
                  </div>
                );
              })
            ) : (
              <div className="text-sm text-gray-400 italic">
                No ProGear groups assigned
              </div>
            )}
          </div>
        </div>

        {/* Agent Access */}
        <div>
          <div className="text-xs text-gray-500 uppercase font-semibold mb-2 flex items-center gap-1">
            <Shield className="w-3 h-3" />
            Agent Access
          </div>
          <div className="space-y-1">
            {matchedGroups.length > 0 ? (
              matchedGroups.map((group) => {
                const info = groupInfo[group];
                return info.access.map((agent, idx) => (
                  <div
                    key={`${group}-${idx}`}
                    className="flex items-center gap-2 text-sm"
                  >
                    <div className="w-2 h-2 rounded-full bg-success-green"></div>
                    <span className="text-gray-600">{agent}</span>
                  </div>
                ));
              })
            ) : (
              <div className="text-sm text-gray-400 italic">
                No agent access configured
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
