# Despliegue temporal en AWS Lightsail

Este despliegue ejecuta frontend, API FastAPI y PostgreSQL en una instancia Lightsail. Docker usa volúmenes persistentes para la base y los aptos médicos; los datos se conservan mientras exista la instancia y sus volúmenes.

## Costos

El paquete Linux/Unix IPv4 de Lightsail con 2 GB cuesta USD 12 por mes. AWS ofrece tres meses gratis para paquetes seleccionados, incluido este, sujeto a elegibilidad y limitado a un paquete por cuenta. Verificá la oferta en tu cuenta antes de crear la instancia. Sin la oferta, Lightsail cobra por hora hasta el máximo mensual y prorratea al eliminar una instancia antes del cierre del mes.

Una IP estática no tiene costo mientras está asociada a una instancia. Al terminar el TP, eliminá la instancia y los snapshots, y eliminá la IP si queda sin asociar.

## Preparación de Lightsail

1. Creá una instancia Ubuntu Linux de 2 GB con IPv4 pública en Virginia y asociá una IP estática.
2. En la red de Lightsail, permití TCP 80 y 443. Permití SSH por TCP 22 solo desde tu IP.
3. Usá un dominio propio o un hostname de `sslip.io` con la IP estática, por ejemplo `203.0.113.10.sslip.io`. Caddy solicita y renueva HTTPS automáticamente si el hostname resuelve a la instancia y los puertos 80/443 son accesibles.
4. Por SSH, instalá Docker y el plugin de Docker Compose. Agregá el usuario de despliegue al grupo `docker`, creá `/opt/set-to-set` y asignáselo a ese usuario. Volvé a iniciar sesión después de agregar el grupo.
5. Cloná en `/opt/set-to-set` la rama que contiene este despliegue. Copiá `deploy/aws/env.example` a `.env` y completá los valores. Reemplazá el hostname de ejemplo; generá valores al azar para `POSTGRES_PASSWORD` y `JWT_SECRET`. No subas `.env` a GitHub.
6. Desde `/opt/set-to-set`, ejecutá:

   ```bash
   docker compose --parallel 1 -f docker-compose.aws.yml up -d --build
   ```

La aplicación queda disponible en `https://<DOMAIN>` y la API en `https://<DOMAIN>/health`.

## Envío de correo

La API usa SMTP. Con Amazon SES, verificá una identidad de envío y usá las credenciales SMTP de SES, no las claves generales de AWS. En sandbox, SES solo permite enviar a destinatarios verificados. Verificá las cuentas de quienes probarán el TP o solicitá a SES acceso de producción para enviar a otras direcciones. SES factura según el volumen de correo.

## Despliegue automático desde GitHub

El workflow `.github/workflows/deploy-lightsail.yml` despliega con cada push o merge en `main`. Antes de integrar el cambio en `main`, prepará la instancia y su `.env`; después agregá estos secretos en **GitHub → Settings → Secrets and variables → Actions**:

- `LIGHTSAIL_HOST`: IP estática.
- `LIGHTSAIL_USER`: usuario SSH, normalmente `ubuntu`.
- `LIGHTSAIL_SSH_PRIVATE_KEY`: clave privada autorizada para ese usuario.

El workflow copia el código y ejecuta Docker Compose. No copia ni reemplaza `.env`, ni borra los volúmenes persistentes.

No ejecutes `docker compose down -v`: el flag `-v` borra PostgreSQL y los archivos cargados.
