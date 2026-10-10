import type {Metadata} from 'next';
import './globals.css';
export const metadata: Metadata={title:'NyayaVault | Evidence Command',description:'Secure digital evidence and chain of custody'};
export default function Layout({children}:{children:React.ReactNode}){return <html lang="en"><body>{children}</body></html>}
