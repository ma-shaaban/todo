import { BrowserRouter, Route, Routes } from 'react-router'
import { AuthProvider, RequireAuth } from './auth.jsx'
import Layout from './components/Layout.jsx'
import Invite from './pages/Invite.jsx'
import Login from './pages/Login.jsx'
import MyTasks from './pages/MyTasks.jsx'
import Notifications from './pages/Notifications.jsx'
import Settings from './pages/Settings.jsx'
import Space from './pages/Space.jsx'
import Spaces from './pages/Spaces.jsx'
import Signup from './pages/Signup.jsx'

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/signup" element={<Signup />} />
          <Route path="/invite/:code" element={<Invite />} />
          <Route
            element={
              <RequireAuth>
                <Layout />
              </RequireAuth>
            }
          >
            <Route path="/" element={<Spaces />} />
            <Route path="/spaces/:id" element={<Space />} />
            <Route path="/me/todos" element={<MyTasks />} />
            <Route path="/notifications" element={<Notifications />} />
            <Route path="/settings" element={<Settings />} />
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}
