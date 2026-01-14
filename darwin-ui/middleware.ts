import { withAuth } from "next-auth/middleware"
import { NextResponse } from "next/server"

export default withAuth(
  function middleware(req) {
    // Allow the request to continue
    return NextResponse.next()
  },
  {
    callbacks: {
      authorized: ({ token, req }) => {
        // Check if user is authenticated
        const isAuth = !!token
        const isAuthPage =
          req.nextUrl.pathname.startsWith("/login") ||
          req.nextUrl.pathname.startsWith("/register") ||
          req.nextUrl.pathname.startsWith("/invites")

        if (isAuthPage) {
          // Allow access to auth pages
          if (isAuth) {
            // Redirect to dashboard if already authenticated
            return false
          }
          return true
        }

        // Require auth for all other pages
        return isAuth
      },
    },
    pages: {
      signIn: "/login",
    },
  }
)

// Protect all routes except public ones
export const config = {
  matcher: [
    /*
     * Match all request paths except for the ones starting with:
     * - api/auth (NextAuth API routes)
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico (favicon file)
     * - public files (images, etc.)
     */
    "/((?!api/auth|_next/static|_next/image|favicon.ico|.*\\.png$|.*\\.jpg$|.*\\.jpeg$|.*\\.svg$).*)",
  ],
}
