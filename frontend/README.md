# InboxAI Frontend

## Description

The frontend of InboxAI provides an intuitive and user-friendly web interface for chat with email. This repository contains the frontend codebase for InboxAI, built using modern web technologies like React, Vite, and TailwindCSS.

This project is built using **React**, **TypeScript**, and **Vite**.

### Installation

Make sure you have [Node.js](https://nodejs.org/) installed.

Clone this repository:

```sh
git clone https://github.com/kprakhar27/InboxAI.git
cd InboxAI/frontend
```

Install dependencies:

```sh
npm install
```

### Running the Project

To start the development server, run:

```sh
npm run dev
```

The app will be available at http://localhost:3000.

### Available Scripts

`npm run dev` - Start the development server.

`npm run build` - Build the production-ready application.

`npm run preview` - Preview the production build.

`npm run lint` - Run ESLint to check for code issues.

### Project Structure

```
frontend/
├── public/ # Static assets
├── src/
│ ├── components/ # Reusable React components
│ ├── pages/ # Application pages
│ ├── hooks/ # Custom React hooks
│ ├── services/ # API service functions
│ ├── utils/ # Utility functions
│ ├── styles/ # Global styles
│ ├── App.tsx # Main application component
│ ├── main.tsx # Entry point
│ └── index.html # HTML template
├── package.json # Project configuration
└── vite.config.ts # Vite configuration
```

### Tech Stack

- Framework: React
- Build Tool: Vite
- Styling: TailwindCSS
- State Management: React Query
- Routing: React Router
- Form Handling: React Hook Form

### Deployment

The application is deployed using **GitHub Pages**. The `gh-pages` package is used to automate the deployment process.
ui-deploy workflow builds and copies the `dist` folder to the `gh-pages` branch of the repository.

The deployed application will be available at [https://inboxai.tech](https://inboxai.tech).
