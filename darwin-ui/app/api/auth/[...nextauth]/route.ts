import NextAuth, { NextAuthOptions, User } from "next-auth"
import CredentialsProvider from "next-auth/providers/credentials"
import axios from "axios"

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

const authOptions: NextAuthOptions = {
  providers: [
    CredentialsProvider({
      name: "Credentials",
      credentials: {
        email: { label: "Email", type: "email" },
        password: { label: "Password", type: "password" },
      },
      async authorize(credentials) {
        if (!credentials?.email || !credentials?.password) {
          throw new Error("Email and password required")
        }

        try {
          // Call Darwin API login endpoint
          const response = await axios.post(`${API_BASE_URL}/api/auth/login`, {
            email: credentials.email,
            password: credentials.password,
          })

          const data = response.data

          if (data.access_token && data.user_id) {
            return {
              id: data.user_id,
              email: credentials.email,
              name: credentials.email.split('@')[0], // Use email prefix as name
              accessToken: data.access_token,
              teamId: data.team_id,
            } as User & {
              accessToken: string
              teamId: string
            }
          }

          return null
        } catch (error: any) {
          console.error("Login error:", error.response?.data || error.message)
          if (error.response?.data?.detail) {
            throw new Error(error.response.data.detail)
          }
          throw new Error("Authentication failed")
        }
      },
    }),
  ],
  callbacks: {
    async jwt({ token, user }) {
      // Persist user data to token
      if (user) {
        token.accessToken = (user as any).accessToken
        token.teamId = (user as any).teamId
        token.id = user.id
      }
      return token
    },
    async session({ session, token }) {
      // Add custom fields to session
      if (token) {
        session.user.id = token.id as string
        session.accessToken = token.accessToken as string
        session.teamId = token.teamId as string
      }
      return session
    },
  },
  pages: {
    signIn: "/login",
    error: "/login",
  },
  session: {
    strategy: "jwt",
    maxAge: 24 * 60 * 60, // 24 hours
  },
  secret: process.env.NEXTAUTH_SECRET,
}

const handler = NextAuth(authOptions)

export { handler as GET, handler as POST }
