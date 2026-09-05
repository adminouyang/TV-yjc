name: IP checkout

on:
  # 手动触发，可指定 city_choice（1~35，0 或留空表示全部）
  workflow_dispatch:
    inputs:
      city_choice:
        description: "城市选项（1~35，0 或全部留空=测试全部城市）"
        required: false
        default: "0"

  # 定时触发（UTC 时间，示例：每日 02:00 = 北京时间 10:00）
  schedule:
    - cron: "0 2 * * *"

env:
  BASE_DIR: "TV-yjc/IP_Scan"
  RESULT_DIR: "TV-yjc/IP_Scan/checkout_ip/result_ip_file"

jobs:
  scan:
    runs-on: ubuntu-latest

    steps:
      # 1. 检出仓库代码（含 checkout_ip.sh 脚本）
      - name: Checkout repository
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      # 2. 安装依赖（nc、curl）
      - name: Install dependencies
        run: |
          sudo apt-get update
          sudo apt-get install -y netcat-openbsd curl

      # 3. 赋予脚本可执行权限
      - name: Make script executable
        run: chmod +x ${BASE_DIR}/checkout_ip.sh

      # 4. 运行 IP 测速脚本
      #    - 定时触发：测试全部城市（传入 0）
      #    - 手动触发：使用输入的 city_choice
      - name: Run IP scan script
        working-directory: ${{ github.workspace }}
        run: |
          mkdir -p ${RESULT_DIR}
          if [ "${{ github.event_name }}" = "workflow_dispatch" ]; then
            bash ${BASE_DIR}/checkout_ip.sh ${{ github.event.inputs.city_choice }}
          else
            bash ${BASE_DIR}/checkout_ip.sh 0
          fi

      # 5. 上传结果文件为可下载产物（保留 30 天）
      - name: Upload result artifacts
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: scan-results-${{ github.run_number }}
          path: ${{ env.RESULT_DIR }}/*.txt
          retention-days: 30

      # 6. 将结果变更提交回仓库
      - name: Commit and push results
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add ${RESULT_DIR}/ || true
          # 无变更则跳过提交
          if git diff --cached --quiet; then
            echo "No changes to commit"
          else
            git commit -m "chore: update scan results [skip ci]"
            git push
          fi
