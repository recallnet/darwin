import "next-auth"
import { DefaultSession } from "next-auth"

declare module "next-auth" {
  interface Session {
    user: {
      id: string
    } & DefaultSession["user"]
    accessToken: string
    teamId: string
    role: string
  }

  interface User {
    id: string
    email: string
    name: string
    accessToken: string
    teamId: string
    role: string
  }
}

declare module "next-auth/jwt" {
  interface JWT {
    id: string
    accessToken: string
    teamId: string
    role: string
  }
}
