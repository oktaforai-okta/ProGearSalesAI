import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import Script from 'next/script';
import './globals.css';
import { Providers } from '@/components/Providers';

const inter = Inter({ subsets: ['latin'] });

export const metadata: Metadata = {
  title: 'ProGear Sales AI',
  description: 'AI-powered sales assistant secured by Okta and FGA',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={inter.className}>
        <Script id="progear-theme-init" strategy="beforeInteractive">
          {`(() => {
            try {
              const value = localStorage.getItem('progear-color-theme');
              const theme = value === 'dark' || value === 'system' ? value : 'light';
              const dark = theme === 'dark' || (theme === 'system' && matchMedia('(prefers-color-scheme: dark)').matches);
              document.documentElement.classList.toggle('dark', dark);
              document.documentElement.dataset.theme = theme;
              document.documentElement.style.colorScheme = dark ? 'dark' : 'light';
            } catch {
              document.documentElement.dataset.theme = 'light';
            }
          })();`}
        </Script>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
