/**
 * MnesOS Alpha Web Client — Main Application.
 *
 * Thin composition root. All UI logic lives in the context providers and AppShell.
 * Fixed in MNS-260521-04: decomposed God Component into AuthProvider,
 * GameInstanceProvider, and AppShell.
 */

import { AuthProvider } from "./contexts/AuthContext";
import { GameInstanceProvider } from "./contexts/GameInstanceContext";
import AppShell from "./components/AppShell";
import "./App.css";

function App() {
  return (
    <AuthProvider>
      <GameInstanceProvider>
        <AppShell />
      </GameInstanceProvider>
    </AuthProvider>
  );
}

export default App;

