#!/bin/bash
set -euo pipefail
fail() {
    printf '%s\n' "$1" >&2
    if [ -n "${TRIM_TEMP_LOGFILE:-}" ]; then printf '%s\n' "$1" > "$TRIM_TEMP_LOGFILE"; fi
    exit 1
}
[ -n "${TRIM_APPNAME:-}" ] || fail '缺少应用标识'
case "$TRIM_APPNAME" in
    openviking) CONTAINER_NAME=openviking-fnos ;;
    openviking-local) CONTAINER_NAME=openviking-fnos-local ;;
    *) fail '应用标识无效' ;;
esac
[ -n "${TRIM_PKGVAR:-}" ] && [ -d "$TRIM_PKGVAR" ] || fail '应用数据目录不可用'
case "$TRIM_PKGVAR" in /*) ;; *) fail '应用数据目录必须为绝对路径';; esac
[ "$TRIM_PKGVAR" != / ] || fail '应用数据目录无效'
[ -f "${TRIM_APPDEST}/settings.json" ] || fail '应用资源不可用'
# These values are generated at build time, never supplied by a wizard.
IMAGE=$(sed -n 's/.*"image": "\([^"]*\)".*/\1/p' "$TRIM_APPDEST/settings.json")
VARIANT=$(sed -n 's/.*"variant": "\([^"]*\)".*/\1/p' "$TRIM_APPDEST/settings.json")
case "$VARIANT" in standard|local) ;; *) fail '应用模式无效';; esac
[ -n "$IMAGE" ] || fail '镜像设置为空'
helper() {
    docker run --rm -i --network none --log-driver none \
        --mount "type=bind,src=$TRIM_PKGVAR,dst=/state" \
        --mount "type=bind,src=$TRIM_APPDEST/tools,dst=/helper,readonly" \
        --entrypoint python "$IMAGE" /helper/configure.py "$@"
}
configure() {
    printf '%s\0' "${wizard_root_key:-}" "${wizard_embed_base:-}" \
        "${wizard_embed_model:-}" "${wizard_embed_key:-}" "${wizard_embed_dimension:-}" \
        | helper configure "$VARIANT" || fail '配置保存失败；检查设置、目录权限和索引兼容性'
}
prepare_storage() {
    local path documents='' models=''
    local -a shares model_mounts
    IFS=':' read -r -a shares <<< "${TRIM_DATA_SHARE_PATHS:-}"
    for path in "${shares[@]}"; do
        case "$path" in
            /*/openviking/documents) documents=$(readlink -f -- "$path") ;;
            /*/openviking/models) models=$(readlink -f -- "$path") ;;
        esac
    done
    [ -n "$documents" ] && [ -d "$documents" ] || fail '飞牛未创建文档共享目录，请检查应用文件资源'
    [ -n "$models" ] && [ -d "$models" ] || fail '飞牛未创建模型共享目录，请检查应用文件资源'
    model_mounts=()
    if [ "$VARIANT" = local ]; then
        model_mounts=(--mount "type=bind,src=$TRIM_APPDEST/models,dst=/bundled-models,readonly"
                      --mount "type=bind,src=$models,dst=/shared-models")
    fi
    printf '%s\0' "$documents" "$models" "$VARIANT" |
        docker run --rm -i --network none --log-driver none \
            --mount "type=bind,src=$TRIM_PKGVAR,dst=/state" \
            --mount "type=bind,src=$TRIM_APPDEST/tools,dst=/helper,readonly" \
            "${model_mounts[@]}" --entrypoint python "$IMAGE" /helper/storage.py || fail '专用目录准备失败，请检查共享目录及模型校验'
}
compose_app() {
    docker compose -p "$TRIM_APPNAME" -f "$TRIM_APPDEST/docker/docker-compose.yaml" \
        -f "$TRIM_PKGVAR/nas-volumes.json" "$@"
}
