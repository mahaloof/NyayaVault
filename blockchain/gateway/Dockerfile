FROM node:22-bookworm-slim
WORKDIR /app
COPY package*.json ./
RUN npm install -g pnpm@10.18.3 && pnpm import && pnpm install --prod --frozen-lockfile
COPY server.mjs ./
USER node
CMD ["node", "server.mjs"]
