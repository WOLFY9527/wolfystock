import type React from 'react';
import HomeBentoDashboardPage from './HomeBentoDashboardPage';
import { useProductSurface } from '../hooks/useProductSurface';

const HomeSurfacePage: React.FC = () => {
  const { isGuest } = useProductSurface();
  return <HomeBentoDashboardPage key={isGuest ? 'guest-home-surface' : 'member-home-surface'} isGuest={isGuest} />;
};

export default HomeSurfacePage;
