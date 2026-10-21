import { Component } from 'react'

/** 全域錯誤邊界：避免單一頁面的例外讓整個應用白畫面。 */
export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { error: null }
  }

  static getDerivedStateFromError(error) {
    return { error }
  }

  componentDidCatch(error, info) {
    console.error('未捕捉的錯誤：', error, info)
  }

  render() {
    if (this.state.error) {
      return (
        <div className="container">
          <div className="alert error">
            畫面發生錯誤，請重新整理。若持續發生，請回報給系統管理員。
            <div className="small" style={{ marginTop: 6 }}>
              {String(this.state.error?.message || this.state.error)}
            </div>
          </div>
          <button onClick={() => window.location.reload()}>重新載入</button>
        </div>
      )
    }
    return this.props.children
  }
}
