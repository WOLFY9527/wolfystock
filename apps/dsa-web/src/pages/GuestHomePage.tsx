import type React from 'react';
import { useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { buildLocalizedPath, parseLocaleFromPathname } from '../utils/localeRouting';
import HomeBentoDashboardPage from './HomeBentoDashboardPage';

const GuestHomePage: React.FC = () => {
  const { loggedIn, isLoading: authLoading } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const routeLocale = parseLocaleFromPathname(location.pathname);
  const homePath = routeLocale ? buildLocalizedPath('/', routeLocale) : '/';

  useEffect(() => {
    if (!authLoading && loggedIn) {
      navigate(homePath, { replace: true });
    }
  }, [authLoading, homePath, loggedIn, navigate]);

  if (!authLoading && loggedIn) {
    return null;
  }

  return <HomeBentoDashboardPage isGuest />;
};

export default GuestHomePage;
