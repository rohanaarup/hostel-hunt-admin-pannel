import { redirect } from 'next/navigation';
import { INITIAL_ROUTE } from '@/routing';

export default function Home() {
  redirect(INITIAL_ROUTE);
}