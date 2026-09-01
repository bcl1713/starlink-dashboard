import { Menu, Radio } from 'lucide-react';
import { useState } from 'react';
import { Link, NavLink } from 'react-router-dom';

import { APP_NAVIGATION_ITEMS } from './app-navigation-items';

export function AppNavigation() {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <nav className="border-b bg-card" aria-label="Primary navigation">
      <div className="mx-auto flex min-h-16 max-w-[1440px] items-center justify-between gap-4 px-4 sm:px-6 lg:px-8">
        <Link
          to="/overview"
          className="flex min-h-11 min-w-11 items-center gap-2 font-semibold tracking-tight text-foreground"
          onClick={() => setIsOpen(false)}
        >
          <span className="flex size-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <Radio className="size-4" aria-hidden="true" />
          </span>
          Mission Planner
        </Link>
        <button
          type="button"
          className="inline-flex min-h-11 min-w-11 items-center justify-center rounded-lg border border-input text-foreground lg:hidden"
          aria-label="Toggle navigation"
          aria-expanded={isOpen}
          onClick={() => setIsOpen((open) => !open)}
        >
          <Menu className="size-5" aria-hidden="true" />
        </button>
        <div className="hidden items-center gap-1 lg:flex">
          {APP_NAVIGATION_ITEMS.map(({ to, label }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `inline-flex min-h-11 min-w-11 items-center rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-accent text-primary'
                    : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                }`
              }
            >
              {label}
            </NavLink>
          ))}
        </div>
      </div>
      {isOpen && (
        <div className="border-t bg-card px-4 py-2 lg:hidden">
          <div className="mx-auto grid max-w-[1440px] gap-1">
            {APP_NAVIGATION_ITEMS.map(({ to, label }) => (
              <NavLink
                key={to}
                to={to}
                onClick={() => setIsOpen(false)}
                className={({ isActive }) =>
                  `flex min-h-11 min-w-11 items-center rounded-lg px-3 py-2 text-sm font-medium ${
                    isActive
                      ? 'bg-accent text-primary'
                      : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                  }`
                }
              >
                {label}
              </NavLink>
            ))}
          </div>
        </div>
      )}
    </nav>
  );
}
