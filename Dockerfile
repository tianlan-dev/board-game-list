FROM node:20-bookworm-slim

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .

ENV npm_config_cache=/tmp/.npm

USER node
CMD ["npm", "run", "start"]
