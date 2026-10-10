FROM node:22-bookworm-slim
WORKDIR /app
COPY package*.json ./
RUN npm install -g pnpm@10.18.3 && pnpm import && pnpm install --prod --frozen-lockfile
COPY index.js server.sh ./
RUN sed -i 's/\r$//' server.sh && chmod +x server.sh
USER node
EXPOSE 9999
CMD ["sh", "/app/server.sh"]
